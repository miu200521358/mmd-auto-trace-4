package usecase

import (
	"strings"
	"sync"

	"github.com/cheggaaa/pb/v3"
	"github.com/miu200521358/mlib_go/pkg/mmath"
	"github.com/miu200521358/mlib_go/pkg/mutils/mlog"
	"github.com/miu200521358/mlib_go/pkg/pmx"
	"github.com/miu200521358/mlib_go/pkg/vmd"
)

func Reduce(allPrevMotions []*vmd.VmdMotion, modelPath string) []*vmd.VmdMotion {
	allMotions := make([]*vmd.VmdMotion, len(allPrevMotions))

	// 全体のタスク数をカウント
	totalFrames := len(allPrevMotions)
	for _, rotMotion := range allPrevMotions {
		totalFrames += int(rotMotion.GetMaxFrame()-rotMotion.GetMinFrame()+1.0) * 3
	}

	bar := newProgressBar(totalFrames)
	var wg sync.WaitGroup

	for i := range allPrevMotions {
		wg.Add(1)

		go func(i int, prevMotion *vmd.VmdMotion) {
			defer wg.Done()
			motion := reduceMotion(prevMotion, bar)

			if mlog.IsVerbose() {
				motion.Path = strings.Replace(allPrevMotions[i].Path, "_ground.vmd", "_fix.vmd", -1)
				err := vmd.Write(motion)
				if err != nil {
					mlog.E("Failed to write leg ik vmd: %v", err)
				}
			}

			allMotions[i] = motion
		}(i, allPrevMotions[i])
	}

	wg.Wait()
	bar.Finish()

	return allMotions
}

func reduceMotion(prevMotion *vmd.VmdMotion, bar *pb.ProgressBar) *vmd.VmdMotion {
	motion := vmd.NewVmdMotion(strings.Replace(prevMotion.Path, "_heel.vmd", "_fix.vmd", -1))

	minFno := prevMotion.BoneFrames.GetItem(pmx.CENTER.String()).GetMinFrame()
	maxFno := prevMotion.BoneFrames.GetItem(pmx.CENTER.String()).GetMaxFrame()

	{
		// センター
		xs := make([]float64, int(maxFno-minFno+1))
		ys := make([]float64, int(maxFno-minFno+1))
		zs := make([]float64, int(maxFno-minFno+1))

		for i := 0; i <= int(maxFno-minFno); i += 1 {
			bar.Increment()
			fno := float32(i) + minFno

			bf := prevMotion.BoneFrames.GetItem(pmx.CENTER.String()).GetItem(fno)
			xs[i] = bf.Position.GetX()
			ys[i] = bf.Position.GetY()
			zs[i] = bf.Position.GetZ()
		}

		xInflectionIndexes := mmath.FindInflectionPoints(xs, 0.06)
		yInflectionIndexes := mmath.FindInflectionPoints(ys, 0.06)
		zInflectionIndexes := mmath.FindInflectionPoints(zs, 0.09)

		centerXZInflectionIndexes := mmath.MergeInflectionPoints(xs, []map[int]int{xInflectionIndexes, zInflectionIndexes})

		for i := 0; i <= int(maxFno-minFno); i += 1 {
			fno := float32(i) + minFno
			bar.Increment()

			if _, ok := centerXZInflectionIndexes[i]; ok {
				// XZ (センター)
				appendMoveCurveFrame(motion, pmx.CENTER.String(), fno, float32(centerXZInflectionIndexes[i])+minFno,
					xs[i:(centerXZInflectionIndexes[i]+1)], nil, zs[i:(centerXZInflectionIndexes[i]+1)])
			}
			if _, ok := yInflectionIndexes[i]; ok {
				// Y (グルーブ)
				appendMoveCurveFrame(motion, pmx.GROOVE.String(), fno, float32(yInflectionIndexes[i])+minFno,
					nil, ys[i:(yInflectionIndexes[i]+1)], nil)
			}
		}
	}

	return motion
}

// 移動補間ありのキーフレを追加
func appendMoveCurveFrame(motion *vmd.VmdMotion, boneName string, startFno, endFno float32, xs, ys, zs []float64) {
	startBf := motion.BoneFrames.GetItem(boneName).GetItem(startFno)
	endBf := motion.BoneFrames.GetItem(boneName).GetItem(endFno)

	if ys == nil {
		startBf.Position = &mmath.MVec3{xs[0], 0, zs[0]}
		endBf.Position = &mmath.MVec3{xs[len(xs)-1], 0, zs[len(zs)-1]}
		endBf.Curves.TranslateX = mmath.NewCurveFromValues(xs)
		endBf.Curves.TranslateZ = mmath.NewCurveFromValues(zs)
	} else if xs == nil {
		startBf.Position = &mmath.MVec3{0, ys[0], 0}
		endBf.Position = &mmath.MVec3{0, ys[len(ys)-1], 0}
		endBf.Curves.TranslateY = mmath.NewCurveFromValues(ys)
	} else {
		startBf.Position = &mmath.MVec3{xs[0], ys[0], zs[0]}
		endBf.Position = &mmath.MVec3{xs[len(xs)-1], ys[len(ys)-1], zs[len(zs)-1]}
	}

	if !motion.BoneFrames.GetItem(boneName).Contains(startFno) {
		// まだキーフレがない場合のみ開始キーフレ追加
		motion.AppendRegisteredBoneFrame(boneName, startBf)
	}

	// 終端キーフレは補間ありで登録
	motion.AppendRegisteredBoneFrame(boneName, endBf)
}

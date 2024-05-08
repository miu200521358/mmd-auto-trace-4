package usecase

import (
	"strings"
	"sync"

	"github.com/cheggaaa/pb/v3"
	"github.com/miu200521358/mlib_go/pkg/deform"
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

		// xInflectionIndexes, xNonMoveIndexes := mmath.FindInflectionPoints(xs, 0.05)
		yInflectionIndexes, yNonMoveIndexes := mmath.FindInflectionPoints(ys, 0.04)
		// zInflectionIndexes, zNonMoveIndexes := mmath.FindInflectionPoints(zs, 0.1)

		for i := 0; i <= int(maxFno-minFno); i += 1 {
			fno := float32(i) + minFno
			bar.Increment()

			if _, ok := yInflectionIndexes[i]; ok {
				// 変曲点は補間
				{
					// キーは終了地点（補間を入れるキーフレ）
					endFno := fno
					// 値は開始地点
					startFno := float32(yInflectionIndexes[i]) + minFno
					// 該当区間の値
					clipYs := ys[yInflectionIndexes[i]:(i + 1)]

					if !motion.BoneFrames.GetItem(pmx.GROOVE.String()).Contains(startFno) {
						// まだキーフレがない場合のみ開始キーフレ追加
						startBf := deform.NewBoneFrame(startFno)
						startBf.Position.SetY(prevMotion.BoneFrames.GetItem(pmx.CENTER.String()).GetItem(startFno).Position.GetY())
						motion.AppendRegisteredBoneFrame(pmx.GROOVE.String(), startBf)
					}

					// 終端キーフレ（補間を入れる）
					endBf := deform.NewBoneFrame(endFno)
					endBf.Position.SetY(prevMotion.BoneFrames.GetItem(pmx.CENTER.String()).GetItem(endFno).Position.GetY())
					endBf.Curves.TranslateY = mmath.NewCurveFromValues(clipYs)
					motion.AppendRegisteredBoneFrame(pmx.GROOVE.String(), endBf)
				}
			}
		}

		for i := 0; i <= int(maxFno-minFno); i += 1 {
			fno := float32(i) + minFno
			bar.Increment()

			if _, ok := yNonMoveIndexes[i]; ok {
				// 動かない場所は固定
				// キーは開始地点
				startFno := fno
				// 値は終了地点
				endFno := float32(yNonMoveIndexes[i]) + minFno
				y := prevMotion.BoneFrames.GetItem(pmx.CENTER.String()).GetItem(startFno).Position.GetY()

				if !motion.BoneFrames.GetItem(pmx.GROOVE.String()).Contains(startFno) &&
					!motion.BoneFrames.GetItem(pmx.GROOVE.String()).Contains(startFno-1) &&
					!motion.BoneFrames.GetItem(pmx.GROOVE.String()).Contains(startFno+1) {
					// 直接のキーフレもしくは補間ありの開始キーフレが無い場合のみ登録
					startBf := deform.NewBoneFrame(startFno)
					startBf.Position.SetY(y)
					motion.AppendRegisteredBoneFrame(pmx.GROOVE.String(), startBf)
				}

				if !motion.BoneFrames.GetItem(pmx.GROOVE.String()).Contains(endFno) &&
					!motion.BoneFrames.GetItem(pmx.GROOVE.String()).Contains(endFno-1) &&
					!motion.BoneFrames.GetItem(pmx.GROOVE.String()).Contains(endFno+1) {
					endBf := deform.NewBoneFrame(endFno)
					endBf.Position.SetY(y)
					motion.AppendRegisteredBoneFrame(pmx.GROOVE.String(), endBf)
				}
			}
		}
	}

	return motion
}

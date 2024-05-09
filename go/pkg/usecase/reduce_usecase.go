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

func Reduce(allPrevMotions []*vmd.VmdMotion, modelPath string, moveTolerance, rotTolerance float64, space int) []*vmd.VmdMotion {
	allMotions := make([]*vmd.VmdMotion, len(allPrevMotions))

	// 全体のタスク数をカウント
	totalFrames := len(allPrevMotions)
	for _, rotMotion := range allPrevMotions {
		totalFrames += int(rotMotion.GetMaxFrame()-rotMotion.GetMinFrame()+1.0) * 2
	}

	bar := newProgressBar(totalFrames)
	var wg sync.WaitGroup

	for i := range allPrevMotions {
		wg.Add(1)

		go func(i int, prevMotion *vmd.VmdMotion) {
			defer wg.Done()
			motion := reduceMotion(prevMotion, moveTolerance, rotTolerance, space, bar)

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

func reduceMotion(prevMotion *vmd.VmdMotion, moveTolerance, rotTolerance float64, space int, bar *pb.ProgressBar) *vmd.VmdMotion {
	motion := vmd.NewVmdMotion(strings.Replace(prevMotion.Path, "_heel.vmd", "_fix.vmd", -1))

	minFno := prevMotion.BoneFrames.GetItem(pmx.CENTER.String()).GetMinFrame()
	maxFno := prevMotion.BoneFrames.GetItem(pmx.CENTER.String()).GetMaxFrame()

	{
		// 移動
		moveXs := make(map[string][]float64)
		moveYs := make(map[string][]float64)
		moveZs := make(map[string][]float64)
		for _, boneName := range []string{pmx.CENTER.String(), pmx.LEG_IK.Left(), pmx.LEG_IK.Right()} {
			moveXs[boneName] = make([]float64, int(maxFno-minFno+1))
			moveYs[boneName] = make([]float64, int(maxFno-minFno+1))
			moveZs[boneName] = make([]float64, int(maxFno-minFno+1))
		}

		// 回転
		rots := make(map[string][]float64)
		quats := make(map[string][]*mmath.MQuaternion)
		for boneName := range prevMotion.BoneFrames.Data {
			if boneName != pmx.CENTER.String() {
				rots[boneName] = make([]float64, int(maxFno-minFno+1))
				quats[boneName] = make([]*mmath.MQuaternion, int(maxFno-minFno+1))
			}
		}

		for i := 0; i <= int(maxFno-minFno); i += 1 {
			bar.Increment()
			fno := float32(i) + minFno

			for boneName := range prevMotion.BoneFrames.Data {
				if _, ok := moveXs[boneName]; ok {
					bf := prevMotion.BoneFrames.GetItem(boneName).GetItem(fno)
					moveXs[boneName][i] = bf.Position.GetX()
					moveYs[boneName][i] = bf.Position.GetY()
					moveZs[boneName][i] = bf.Position.GetZ()
				}
				if _, ok := rots[boneName]; ok {
					bf := prevMotion.BoneFrames.GetItem(boneName).GetItem(fno)
					if i == 0 {
						rots[boneName][i] = 1.0
					} else {
						rots[boneName][i] = bf.Rotation.GetQuaternion().Dot(prevMotion.BoneFrames.GetItem(boneName).GetItem(fno - 1).Rotation.GetQuaternion())
					}
					quats[boneName][i] = bf.Rotation.GetQuaternion()
				}
			}
		}

		moveXInflections := make(map[string]map[int]int)
		moveYInflections := make(map[string]map[int]int)
		moveZInflections := make(map[string]map[int]int)

		for boneName := range moveXs {
			if boneName != pmx.LEG_IK.Left() && boneName != pmx.LEG_IK.Right() {
				moveXInflections[boneName] = mmath.FindInflectionPoints(moveXs[boneName], moveTolerance, space)
				moveYInflections[boneName] = mmath.FindInflectionPoints(moveYs[boneName], moveTolerance, space)
				moveZInflections[boneName] = mmath.FindInflectionPoints(moveZs[boneName], moveTolerance, space)
			} else {
				moveXInflections[boneName] = mmath.FindInflectionPoints(moveXs[boneName], 0.12, space)
				moveYInflections[boneName] = mmath.FindInflectionPoints(moveYs[boneName], 0.12, space)
				moveZInflections[boneName] = mmath.FindInflectionPoints(moveZs[boneName], 0.12, space)
			}
		}

		rotInflections := make(map[string]map[int]int)

		for boneName := range rots {
			if boneName != pmx.LEG_IK.Left() && boneName != pmx.LEG_IK.Right() {
				rotInflections[boneName] = mmath.FindInflectionPoints(rots[boneName], rotTolerance, space)
			} else {
				rotInflections[boneName] = mmath.FindInflectionPoints(rots[boneName], 0.001, space)
			}
		}

		centerXZInflections := mmath.MergeInflectionPoints(moveXs[pmx.CENTER.String()],
			[]map[int]int{moveXInflections[pmx.CENTER.String()], moveZInflections[pmx.CENTER.String()]}, space)
		leftLegIkInflections := mmath.MergeInflectionPoints(moveXs[pmx.LEG_IK.Left()],
			[]map[int]int{moveXInflections[pmx.LEG_IK.Left()], moveYInflections[pmx.LEG_IK.Left()],
				moveZInflections[pmx.LEG_IK.Left()], rotInflections[pmx.LEG_IK.Left()]}, space)
		rightLegIkInflections := mmath.MergeInflectionPoints(moveXs[pmx.LEG_IK.Right()],
			[]map[int]int{moveXInflections[pmx.LEG_IK.Right()], moveYInflections[pmx.LEG_IK.Right()],
				moveZInflections[pmx.LEG_IK.Right()], rotInflections[pmx.LEG_IK.Right()]}, space)

		delete(rotInflections, pmx.LEG_IK.Left())
		delete(rotInflections, pmx.LEG_IK.Right())

		for i := 0; i <= int(maxFno-minFno); i += 1 {
			fno := float32(i) + minFno
			bar.Increment()

			if _, ok := centerXZInflections[i]; ok {
				// XZ (センター)
				inflectionIndex := centerXZInflections[i]
				appendCurveFrame(motion, pmx.CENTER.String(), fno, float32(inflectionIndex)+minFno,
					moveXs[pmx.CENTER.String()][i:(inflectionIndex+1)], nil, moveZs[pmx.CENTER.String()][i:(inflectionIndex+1)], nil)
			}
			if _, ok := moveYInflections[pmx.CENTER.String()][i]; ok {
				// Y (グルーブ)
				inflectionIndex := moveYInflections[pmx.CENTER.String()][i]
				appendCurveFrame(motion, pmx.GROOVE.String(), fno, float32(inflectionIndex)+minFno,
					nil, moveYs[pmx.CENTER.String()][i:(inflectionIndex+1)], nil, nil)
			}
			if _, ok := leftLegIkInflections[i]; ok {
				// 左足IK
				inflectionIndex := leftLegIkInflections[i]
				appendCurveFrame(motion, pmx.LEG_IK.Left(), fno, float32(inflectionIndex)+minFno,
					moveXs[pmx.LEG_IK.Left()][i:(inflectionIndex+1)], moveYs[pmx.LEG_IK.Left()][i:(inflectionIndex+1)], moveZs[pmx.LEG_IK.Left()][i:(inflectionIndex+1)],
					quats[pmx.LEG_IK.Left()][i:(inflectionIndex+1)])
			}
			if _, ok := rightLegIkInflections[i]; ok {
				// 右足IK
				inflectionIndex := rightLegIkInflections[i]
				appendCurveFrame(motion, pmx.LEG_IK.Right(), fno, float32(inflectionIndex)+minFno,
					moveXs[pmx.LEG_IK.Right()][i:(inflectionIndex+1)], moveYs[pmx.LEG_IK.Right()][i:(inflectionIndex+1)], moveZs[pmx.LEG_IK.Right()][i:(inflectionIndex+1)],
					quats[pmx.LEG_IK.Right()][i:(inflectionIndex+1)])
			}
			for boneName, rotInflection := range rotInflections {
				// 回転ボーン
				if _, ok := rotInflection[i]; ok {
					inflectionIndex := rotInflection[i]
					appendCurveFrame(motion, boneName, fno, float32(inflectionIndex)+minFno,
						nil, nil, nil, quats[boneName][i:(inflectionIndex+1)])
				}
			}
		}
	}

	return motion
}

func appendCurveFrame(motion *vmd.VmdMotion, boneName string, startFno, endFno float32, xs, ys, zs []float64, quats []*mmath.MQuaternion) {
	startBf := motion.BoneFrames.GetItem(boneName).GetItem(startFno)
	endBf := motion.BoneFrames.GetItem(boneName).GetItem(endFno)

	if xs != nil && ys == nil && zs != nil {
		startBf.Position = &mmath.MVec3{xs[0], 0, zs[0]}
		endBf.Position = &mmath.MVec3{xs[len(xs)-1], 0, zs[len(zs)-1]}
		endBf.Curves.TranslateX = mmath.NewCurveFromValues(xs)
		endBf.Curves.TranslateZ = mmath.NewCurveFromValues(zs)
	} else if xs == nil && ys != nil && zs == nil {
		startBf.Position = &mmath.MVec3{0, ys[0], 0}
		endBf.Position = &mmath.MVec3{0, ys[len(ys)-1], 0}
		endBf.Curves.TranslateY = mmath.NewCurveFromValues(ys)
	} else if xs != nil && ys != nil && zs != nil {
		startBf.Position = &mmath.MVec3{xs[0], ys[0], zs[0]}
		endBf.Position = &mmath.MVec3{xs[len(xs)-1], ys[len(ys)-1], zs[len(zs)-1]}
		endBf.Curves.TranslateX = mmath.NewCurveFromValues(xs)
		endBf.Curves.TranslateY = mmath.NewCurveFromValues(ys)
		endBf.Curves.TranslateZ = mmath.NewCurveFromValues(zs)
	}

	if quats != nil {
		startBf.Rotation.SetQuaternion(quats[0])
		endBf.Rotation.SetQuaternion(quats[len(quats)-1])
		rotTs := make([]float64, len(quats))
		for i, rot := range quats {
			if i == 0 {
				rotTs[i] = 0
			} else if i == len(quats)-1 {
				rotTs[i] = 1
			} else {
				rotTs[i] = mmath.FindSlerpT(quats[0], quats[len(quats)-1], rot)
			}
		}
		endBf.Curves.Rotate = mmath.NewCurveFromValues(rotTs)
	}

	if !motion.BoneFrames.GetItem(boneName).Contains(startFno) {
		// まだキーフレがない場合のみ開始キーフレ追加
		motion.AppendRegisteredBoneFrame(boneName, startBf)
	}

	// 終端キーフレは補間ありで登録
	motion.AppendRegisteredBoneFrame(boneName, endBf)
}

package usecase

import (
	"github.com/miu200521358/mlib_go/pkg/mmath"
	"github.com/miu200521358/mlib_go/pkg/mutils/mlog"
	"github.com/miu200521358/mlib_go/pkg/pmx"
	"github.com/miu200521358/mlib_go/pkg/vmd"
	"github.com/miu200521358/mmd-auto-trace-4/pkg/model"
	"github.com/miu200521358/mmd-auto-trace-4/pkg/utils"
)

func FixHeel(frames *model.Frames, motion *vmd.VmdMotion, modelPath string, motionNum, allNum int) *vmd.VmdMotion {
	mlog.I("[%d/%d] Fix Heel ...", motionNum, allNum)

	minFrame := motion.BoneFrames.Get(pmx.CENTER.String()).GetMinFrame()
	maxFrame := motion.BoneFrames.Get(pmx.CENTER.String()).GetMaxFrame()

	bar := utils.NewProgressBar(maxFrame - minFrame)

	threshold := 0.04
	stopThreshold := threshold * 0.5

	var prevLeftAnklePos2 *mmath.MVec2
	var prevRightAnklePos2 *mmath.MVec2

	for i := range maxFrame - minFrame + 1 {
		bar.Increment()
		fno := minFrame + i

		// 2d-jointの足首の位置を取得
		leftAnkleJoint := frames.Frames[fno].Joint2D["OP LAnkle"]
		rightAnkleJoint := frames.Frames[fno].Joint2D["OP RAnkle"]

		if i == 0 {
			prevLeftAnklePos2 = &mmath.MVec2{leftAnkleJoint.X, leftAnkleJoint.Y}
			prevRightAnklePos2 = &mmath.MVec2{rightAnkleJoint.X, rightAnkleJoint.Y}
			continue
		}

		leftAnklePos2 := &mmath.MVec2{leftAnkleJoint.X, leftAnkleJoint.Y}
		rightAnklePos2 := &mmath.MVec2{rightAnkleJoint.X, rightAnkleJoint.Y}

		// 2d-jointの足首の移動量を計算
		leftAnkleDiff2 := leftAnklePos2.Subed(prevLeftAnklePos2)
		rightAnkleDiff2 := rightAnklePos2.Subed(prevRightAnklePos2)

		prevFno := motion.BoneFrames.Get(pmx.CENTER.String()).RegisteredIndexes.Prev(fno)

		leftAnkleDiff3 := mmath.NewMVec3()
		rightAnkleDiff3 := mmath.NewMVec3()

		lt := max(0, (threshold-leftAnkleDiff2.Length())/threshold)
		rt := max(0, (threshold-rightAnkleDiff2.Length())/threshold)

		// ほぼ動いていない場合、足IKを止める
		if 0.0 < lt && lt < 1.0 {
			leftLegIkBf := motion.BoneFrames.Get(pmx.LEG_IK.Left()).Get(fno)
			prevLeftAnklePos3 := motion.BoneFrames.Get(pmx.LEG_IK.Left()).Get(prevFno).Position
			nowLeftAnklePos3 := leftLegIkBf.Position
			leftAnkleDiff3 = prevLeftAnklePos3.Subed(nowLeftAnklePos3)
			leftAnkleDiff3.SetY(0)
			if leftAnkleDiff2.Length() < stopThreshold {
				// 完全停止
				leftLegIkBf.Position.Add(leftAnkleDiff3)
				motion.AppendRegisteredBoneFrame(pmx.LEG_IK.Left(), leftLegIkBf)
				mlog.V("[LEFT STOP][%d] prevAnklePos2: %v, AnklePos2: %v, AnkleDiff2: %v, prevAnklePos3: %v, nowAnklePos3: %v, AnkleDiff3: %v",
					fno, prevLeftAnklePos2, leftAnklePos2, leftAnkleDiff2.Length(), prevLeftAnklePos3, nowLeftAnklePos3, leftAnkleDiff3)
			} else {
				// 緩やかに停止
				leftAnkleDiff3 = leftAnkleDiff3.MulScalar(lt)
				leftLegIkBf.Position.Add(leftAnkleDiff3)
				motion.AppendRegisteredBoneFrame(pmx.LEG_IK.Left(), leftLegIkBf)
				mlog.V("[LEFT MINI STOP][%d] lt: %f, prevAnklePos2: %v, AnklePos2: %v, AnkleDiff2: %v, prevAnklePos3: %v, nowAnklePos3: %v, AnkleDiff3: %v",
					fno, lt, prevLeftAnklePos2, leftAnklePos2, leftAnkleDiff2.Length(), prevLeftAnklePos3, nowLeftAnklePos3, leftAnkleDiff3)
			}
		}

		if 0.0 < rt && rt < 1.0 {
			rightLegIkBf := motion.BoneFrames.Get(pmx.LEG_IK.Right()).Get(fno)
			prevRightAnklePos3 := motion.BoneFrames.Get(pmx.LEG_IK.Right()).Get(prevFno).Position
			nowRightAnklePos3 := rightLegIkBf.Position
			rightAnkleDiff3 = prevRightAnklePos3.Subed(nowRightAnklePos3)
			rightAnkleDiff3.SetY(0)
			if rightAnkleDiff2.Length() < stopThreshold {
				// 完全停止
				rightLegIkBf.Position.Add(rightAnkleDiff3)
				motion.AppendRegisteredBoneFrame(pmx.LEG_IK.Right(), rightLegIkBf)
				mlog.V("[RIGHT STOP][%d] prevAnklePos2: %v, AnklePos2: %v, AnkleDiff2: %v, prevAnklePos3: %v, nowAnklePos3: %v, AnkleDiff3: %v",
					fno, prevRightAnklePos2, rightAnklePos2, rightAnkleDiff2.Length(), prevRightAnklePos3, nowRightAnklePos3, rightAnkleDiff3)
			} else {
				// 緩やかに停止
				rightAnkleDiff3 = rightAnkleDiff3.MulScalar(rt)
				rightLegIkBf.Position.Add(rightAnkleDiff3)
				motion.AppendRegisteredBoneFrame(pmx.LEG_IK.Right(), rightLegIkBf)
				mlog.V("[RIGHT MINI STOP][%d] rt: %f, prevAnklePos2: %v, AnklePos2: %v, AnkleDiff2: %v, prevAnklePos3: %v, nowAnklePos3: %v, AnkleDiff3: %v",
					fno, rt, prevRightAnklePos2, rightAnklePos2, rightAnkleDiff2.Length(), prevRightAnklePos3, nowRightAnklePos3, rightAnkleDiff3)
			}
		}

		if (0.0 < lt && lt < 1.0) || (0.0 < rt && rt < 1.0) {
			// センターは両方の差分の平均分移動させる
			ratioLeftAnkleDiff3 := leftAnkleDiff3.MuledScalar(lt)
			ratioRightAnkleDiff3 := rightAnkleDiff3.MuledScalar(rt)
			meanAnkleDiff := ratioLeftAnkleDiff3.Add(ratioRightAnkleDiff3).MulScalar(0.5)
			centerBf := motion.BoneFrames.Get(pmx.CENTER.String()).Get(fno)
			centerBf.Position.Add(meanAnkleDiff)
			motion.AppendRegisteredBoneFrame(pmx.CENTER.String(), centerBf)

			mlog.V("[CENTER][%d] leftAnkleDiff3: %v, rightAnkleDiff3: %v, ratioLeftAnkleDiff3: %v, ratioRightAnkleDiff3: %v, meanAnkleDiff: %v",
				fno, leftAnkleDiff3, rightAnkleDiff3, ratioLeftAnkleDiff3, ratioRightAnkleDiff3, meanAnkleDiff)
		}
	}

	bar.Finish()

	return motion
}

package usecase

import (
	"fmt"
	"math"

	"github.com/miu200521358/mlib_go/pkg/mmath"
	"github.com/miu200521358/mlib_go/pkg/mutils"
	"github.com/miu200521358/mlib_go/pkg/mutils/mlog"
	"github.com/miu200521358/mlib_go/pkg/pmx"
	"github.com/miu200521358/mlib_go/pkg/vmd"
	"github.com/miu200521358/mmd-auto-trace-4/pkg/utils"
)

func FixGround(prevMotion *vmd.VmdMotion, modelPath string, motionNum, allNum int) *vmd.VmdMotion {
	mlog.I("[%d/%d] Fix Ground ...", motionNum, allNum)

	// モデル読み込み
	pr := &pmx.PmxReader{}
	data, err := pr.ReadByFilepath(modelPath)
	if err != nil {
		mlog.E("Failed to read pmx: %v", err)
	}
	model := data.(*pmx.PmxModel)

	return setGroundedFootMotion(model, prevMotion)
}

func setGroundedFootMotion(model *pmx.PmxModel, motion *vmd.VmdMotion) *vmd.VmdMotion {
	minFrame := motion.BoneFrames.Get(pmx.CENTER.String()).GetMinFrame()
	maxFrame := motion.BoneFrames.Get(pmx.CENTER.String()).GetMaxFrame()

	bar := utils.NewProgressBar((maxFrame - minFrame) * 3)

	legIkYs := make([]float64, 0, int(maxFrame)-int(minFrame)+1)

	for fno := minFrame; fno <= maxFrame; fno++ {
		bar.Increment()

		leftY := motion.BoneFrames.Get(pmx.LEG_IK.Left()).Get(fno).Position.GetY()
		rightY := motion.BoneFrames.Get(pmx.LEG_IK.Right()).Get(fno).Position.GetY()

		mlog.V("fno: %d, left: %f, right: %f", fno, leftY, rightY)

		legIkYs = append(legIkYs, min(leftY, rightY))
	}

	// 足ＩＫ-Y値全体の9割の場所を接地点とする
	groundY := percentile(legIkYs, 0.9)
	mlog.V("groundY: %f", groundY)

	for fno := minFrame; fno <= maxFrame; fno++ {
		bar.Increment()

		newLeftY := motion.BoneFrames.Get(pmx.LEG_IK.Left()).Get(fno).Position.GetY() - groundY
		newRightY := motion.BoneFrames.Get(pmx.LEG_IK.Right()).Get(fno).Position.GetY() - groundY

		newMinY := min(newLeftY, newRightY)

		frameGroundY := groundY
		if newMinY < 0.0 {
			frameGroundY += newMinY
		}

		newLeftY = motion.BoneFrames.Get(pmx.LEG_IK.Left()).Get(fno).Position.GetY() - frameGroundY
		if newLeftY < 0.2 {
			newLeftY = 0.0
		}
		newRightY = motion.BoneFrames.Get(pmx.LEG_IK.Right()).Get(fno).Position.GetY() - frameGroundY
		if newRightY < 0.2 {
			newRightY = 0.0
		}

		leftLegIkBf := motion.BoneFrames.Get(pmx.LEG_IK.Left()).Get(fno)
		leftLegIkBf.Position.SetY(newLeftY)
		motion.AppendRegisteredBoneFrame(pmx.LEG_IK.Left(), leftLegIkBf)

		rightLegIkBf := motion.BoneFrames.Get(pmx.LEG_IK.Right()).Get(fno)
		rightLegIkBf.Position.SetY(newRightY)
		motion.AppendRegisteredBoneFrame(pmx.LEG_IK.Right(), rightLegIkBf)

		centerBf := motion.BoneFrames.Get(pmx.CENTER.String()).Get(fno)
		centerBf.Position.SetY(centerBf.Position.GetY() - frameGroundY)
		motion.AppendRegisteredBoneFrame(pmx.CENTER.String(), centerBf)
	}

	for fno := minFrame; fno <= maxFrame; fno++ {
		bar.Increment()

		// IFをOFFにした状態での位置関係を取得
		deltas := motion.BoneFrames.Deform(fno, model, []string{
			"左つま先親",
			"左つま先子",
			"左かかと",
			"右つま先親",
			"右つま先子",
			"右かかと",
			pmx.TOE.Left(),
			pmx.TOE.Right(),
			pmx.ANKLE.Left(),
			pmx.ANKLE.Right(),
			pmx.LEG_IK.Left(),
			pmx.LEG_IK.Right(),
		}, false, false, false, nil)

		// Yが0の場合、足首の向きを調整して接地させる
		for _, direction := range []string{"右", "左"} {
			heelBoneName := fmt.Sprintf("%sかかと", direction)
			toeBigBoneName := fmt.Sprintf("%sつま先親", direction)
			toeSmallBoneName := fmt.Sprintf("%sつま先子", direction)
			ankleBoneName := pmx.ANKLE.StringFromDirection(direction)
			legIkBoneName := pmx.LEG_IK.StringFromDirection(direction)

			if motion.BoneFrames.Get(legIkBoneName).Get(fno).Position.GetY() == 0.0 {
				toeBigPos := deltas.GetByName(toeBigBoneName).GlobalPosition()
				toeSmallPos := deltas.GetByName(toeSmallBoneName).GlobalPosition()
				heelPos := deltas.GetByName(heelBoneName).GlobalPosition()

				horizontalQuat := calcHorizontalQuat(toeBigPos, toeSmallPos, heelPos, direction)
				ankleQuat := motion.BoneFrames.Get(ankleBoneName).Get(fno).Rotation.GetQuaternion()

				mlog.D("fno: %d, direction: %s, ankle:%s(%s)(%s), horizontal: %s(%s)(%s)", fno, direction,
					ankleQuat.ToDegrees().String(),
					ankleQuat.String(),
					ankleQuat.MMD().ToDegrees().String(),
					horizontalQuat.ToDegrees().String(),
					horizontalQuat.String(),
					horizontalQuat.MMD().ToDegrees().String(),
				)

				mlog.D("fno: %d, direction: %s, ankleQuat1: %s(%s)(%s)", fno, direction,
					motion.BoneFrames.Get(ankleBoneName).Get(fno).Rotation.GetQuaternion().ToDegrees().String(),
					motion.BoneFrames.Get(ankleBoneName).Get(fno).Rotation.GetQuaternion().String(),
					horizontalQuat.ToDegrees().String(),
					horizontalQuat.String(),
					ankleQuat.Muled(horizontalQuat).ToDegrees().String(),
					ankleQuat.Muled(horizontalQuat).String(),
					ankleQuat.Muled(horizontalQuat.Inverted()).ToDegrees().String(),
					ankleQuat.Muled(horizontalQuat.Inverted()).String(),
					ankleQuat.Inverted().Muled(horizontalQuat).ToDegrees().String(),
					ankleQuat.Inverted().Muled(horizontalQuat).String(),
					horizontalQuat.Muled(ankleQuat).ToDegrees().String(),
					horizontalQuat.Muled(ankleQuat).String(),
					horizontalQuat.Muled(ankleQuat.Inverted()).ToDegrees().String(),
					horizontalQuat.Muled(ankleQuat.Inverted()).String(),
					horizontalQuat.Inverted().Muled(ankleQuat).ToDegrees().String(),
					horizontalQuat.Inverted().Muled(ankleQuat).String(),
				)

				// 足首の向きを調整する角度
				groundAnkleQuat := motion.BoneFrames.Get(ankleBoneName).Get(fno).Rotation.GetQuaternion().Muled(horizontalQuat.Inverted())
				motion.BoneFrames.Get(ankleBoneName).Get(fno).Rotation.SetQuaternion(groundAnkleQuat)

				// 足ＩＫの向きを調整する角度
				groundLegIkQuat := motion.BoneFrames.Get(legIkBoneName).Get(fno).Rotation.GetQuaternion().Muled(horizontalQuat.Inverted())
				motion.BoneFrames.Get(legIkBoneName).Get(fno).Rotation.SetQuaternion(groundLegIkQuat)

				continue
			}
		}

	}

	bar.Finish()

	return motion
}

func percentile(values []float64, percent float64) float64 {
	mutils.SortFloat64s(values)
	// percentに応じた中央値を取得
	middle := int(float64(len(values)) * percent)
	median := values[middle]
	if len(values)%2 == 0 {
		median = (values[middle-1] + values[middle]) / 2
	}

	return median
}

func calcHorizontalQuat(bigToePos, smallToePos, heelPos *mmath.MVec3, direction string) *mmath.MQuaternion {
	// Create vectors for the sides of the triangle
	v1 := smallToePos.Subed(heelPos)
	v2 := bigToePos.Subed(heelPos)

	var up *mmath.MVec3
	if direction == "右" {
		up = mmath.MVec3UnitY
	} else {
		up = mmath.MVec3UnitYInv
	}

	normal := v1.Normalize().Cross(v2.Normalize()).Normalize()

	// 回転軸
	axis := normal.Cross(up).Normalize()
	if math.Abs(axis.Length()) <= 1e-8 {
		return mmath.NewMQuaternion()
	}

	// 回転角
	rad := math.Acos(mmath.ClampFloat(normal.Dot(up), -1.0, 1.0))

	return mmath.NewMQuaternionFromAxisAngles(axis, rad).MMD()
}

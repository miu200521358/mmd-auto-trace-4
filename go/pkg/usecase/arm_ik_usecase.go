package usecase

import (
	"fmt"
	"math"
	"strings"

	"github.com/miu200521358/mlib_go/pkg/mmath"
	"github.com/miu200521358/mlib_go/pkg/mutils/mlog"
	"github.com/miu200521358/mlib_go/pkg/pmx"
	"github.com/miu200521358/mlib_go/pkg/vmd"
	"github.com/miu200521358/mmd-auto-trace-4/pkg/utils"
)

func ConvertArmIk(prevMotion *vmd.VmdMotion, modelPath string, motionNum, allNum int) *vmd.VmdMotion {
	mlog.I("[%d/%d] Convert Arm Ik ...", motionNum, allNum)

	pr := &pmx.PmxReader{}

	// 腕捩IK用モデルを読み込み
	armTwistIkData, err := pr.ReadByFilepath(strings.Replace(modelPath, ".pmx", "_arm_twist_ik.pmx", -1))
	if err != nil {
		mlog.E("Failed to read pmx: %v", err)
	}
	armTwistIkModel := armTwistIkData.(*pmx.PmxModel)
	armTwistIkModel.SetUp()

	minFrame := prevMotion.BoneFrames.Get(pmx.CENTER.String()).GetMinFrame()
	maxFrame := prevMotion.BoneFrames.Get(pmx.CENTER.String()).GetMaxFrame()

	loopLimit := 100
	bar := utils.NewProgressBar(maxFrame - minFrame)

	armIkMotion := prevMotion.Copy().(*vmd.VmdMotion)

	for fno := minFrame; fno <= maxFrame; fno++ {
		bar.Increment()

		convertArmIkMotion(prevMotion, armIkMotion, "右", fno, armTwistIkModel, loopLimit)
		convertArmIkMotion(prevMotion, armIkMotion, "左", fno, armTwistIkModel, loopLimit)
	}

	armIkMotion.BoneFrames.Delete("左腕捩ＩＫ")
	armIkMotion.BoneFrames.Delete("左手捩ＩＫ")
	armIkMotion.BoneFrames.Delete("右腕捩ＩＫ")
	armIkMotion.BoneFrames.Delete("右手捩ＩＫ")

	bar.Finish()

	return armIkMotion
}

func convertArmIkMotion(
	prevMotion, armIkMotion *vmd.VmdMotion, direction string, fno int, armTwistIkModel *pmx.PmxModel, loopLimit int,
) {

	armBoneName := pmx.ARM.StringFromDirection(direction)
	elbowBoneName := pmx.ELBOW.StringFromDirection(direction)
	wristBoneName := pmx.WRIST.StringFromDirection(direction)
	middleTailBoneName := pmx.MIDDLE_TAIL.StringFromDirection(direction)
	armTwistBoneName := pmx.ARM_TWIST.StringFromDirection(direction)
	wristTwistBoneName := pmx.WRIST_TWIST.StringFromDirection(direction)
	armTwistIkBoneName := fmt.Sprintf("%s腕捩ＩＫ", direction)
	// wristTwistIkBoneName := fmt.Sprintf("%s手捩ＩＫ", direction)
	thumbZBoneName := fmt.Sprintf("%s親指Z垂線", direction)

	// IKなしの変化量を取得
	armIkOffDeltas := prevMotion.AnimateBone(fno, armTwistIkModel,
		[]string{armBoneName, elbowBoneName, wristBoneName, middleTailBoneName, thumbZBoneName,
			armTwistBoneName, wristTwistBoneName, armTwistIkBoneName}, false)

	// 腕IK --------------------

	// 腕捩ＩＫは手首の位置を基準とする
	armTwistIkBf := vmd.NewBoneFrame(fno)
	wristOffDelta := armIkOffDeltas.Get(wristBoneName)
	armTwistIkBf.Position = wristOffDelta.Position.Subed(
		armTwistIkModel.Bones.GetByName(armTwistIkBoneName).Position)
	armIkMotion.AppendBoneFrame(armTwistIkBoneName, armTwistIkBf)

	// middleTailOffDelta := armIkOffDeltas.Get(middleTailBoneName, fno)

	// 腕の捩りを除去する
	armOffDelta := armIkOffDeltas.Get(armBoneName)
	_, _, _, armYZQuat := armOffDelta.FrameRotation.SeparateByAxis(
		armTwistIkModel.Bones.GetByName(armBoneName).NormalizedLocalAxisX)
	armBf := vmd.NewBoneFrame(fno)
	armBf.Rotation = mmath.NewRotationByQuaternion(armYZQuat)
	armIkMotion.AppendRegisteredBoneFrame(armBoneName, armBf)

	// ひじをローカルY軸に対して曲げる
	elbowOffDelta := armIkOffDeltas.Get(elbowBoneName)
	_, _, _, elbowYZQuat := elbowOffDelta.FrameRotation.SeparateByAxis(
		armTwistIkModel.Bones.GetByName(elbowBoneName).NormalizedLocalAxisX)
	elbowBf := vmd.NewBoneFrame(fno)
	elbowQuat := mmath.NewMQuaternionFromAxisAngles(
		armTwistIkModel.Bones.GetByName(elbowBoneName).NormalizedLocalAxisY, elbowYZQuat.ToRadian())
	elbowBf.Rotation = mmath.NewRotationByQuaternion(elbowQuat)
	armIkMotion.AppendRegisteredBoneFrame(elbowBoneName, elbowBf)

	// if mlog.IsIkVerbose() {
	// 	armIkMotion.Path = strings.Replace(prevMotion.Path, "heel.vmd", direction+"_arm_ik_0.vmd", -1)
	// 	err := vmd.Write(armIkMotion)
	// 	if err != nil {
	// 		mlog.E("Failed to write arm ik vmd: %v", err)
	// 	}
	// }

	var wristIkOnDeltas *vmd.BoneDeltas
	var armTwistQuat *mmath.MQuaternion
	armKey := math.MaxFloat64
	for j := range loopLimit {
		// IKありの変化量を取得
		wristIkOnDeltas = armIkMotion.AnimateBoneContinueIk(fno, armTwistIkModel,
			[]string{armBoneName, elbowBoneName, wristBoneName, middleTailBoneName, thumbZBoneName,
				armTwistBoneName, wristTwistBoneName, armTwistIkBoneName}, true)

		armTwistOnDelta := wristIkOnDeltas.Get(armTwistBoneName)
		elbowOnDelta := wristIkOnDeltas.Get(elbowBoneName)
		wristOnDelta := wristIkOnDeltas.Get(wristBoneName)
		elbowDistance := elbowOnDelta.Position.Distance(elbowOffDelta.Position)
		wristDistance := wristOnDelta.Position.Distance(wristOffDelta.Position)

		keySum := elbowDistance + wristDistance
		mlog.V("[Arm] Distance [%d][%s][%d] elbow: %f, wrist: %f, keySum: %f, armKey: %f",
			fno, direction, j, elbowDistance, wristDistance, keySum, armKey)

		if keySum < armKey {
			armKey = keySum
			armTwistQuat = armTwistOnDelta.FrameRotationWithoutEffect

			mlog.V("[Arm] Update IK [%d][%s][%d] elbow: %f, wrist: %f, keySum: %f, armKey: %f",
				fno, direction, j, elbowDistance, wristDistance, keySum, armKey)
		}

		if elbowDistance < 1e-2 && wristDistance < 1e-2 {
			mlog.V("*** [Arm] Converged at [%d][%s][%d] elbow: %f, wrist: %f, keySum: %f, armKey: %f",
				fno, direction, j, elbowDistance, wristDistance, keySum, armKey)
			break
		}
	}

	// 最も近いものを採用
	mlog.V("[Arm] FIX Converged at [%d][%s] distance: %f", fno, direction, armKey)

	// FKの各キーフレに値を設定
	armTwistBf := vmd.NewBoneFrame(fno)
	armTwistBf.Rotation = mmath.NewRotationByQuaternion(armTwistQuat)
	armIkMotion.AppendRegisteredBoneFrame(armTwistBoneName, armTwistBf)

	// if mlog.IsIkVerbose() {
	// 	armIkMotion.Path = strings.Replace(prevMotion.Path, "heel.vmd", direction+"_arm_ik_1.vmd", -1)
	// 	err := vmd.Write(armIkMotion)
	// 	if err != nil {
	// 		mlog.E("Failed to write arm ik vmd: %v", err)
	// 	}
	// }

	// // 手捩IK --------------------

	// // 手捩IKは親指Z垂線の位置を基準とする
	// wristTwistIkBf := vmd.NewBoneFrame(fno)
	// thumbZOffDelta := armIkOffDeltas.Get(thumbZBoneName, fno)
	// wristTwistIkBf.Position = thumbZOffDelta.Position.Subed(
	// 	wristTwistIkModel.Bones.GetByName(wristTwistIkBoneName).Position)
	// armIkMotion.AppendBoneFrame(wristTwistIkBoneName, wristTwistIkBf)

	// // 手首の捩りを除去する
	// _, _, _, wristYZQuat := wristOffDelta.FrameRotation.SeparateByAxis(
	// 	armTwistIkModel.Bones.GetByName(wristBoneName).NormalizedLocalAxisX)
	// wristBf := vmd.NewBoneFrame(fno)
	// wristBf.Rotation.SetQuaternion(wristYZQuat)
	// armIkMotion.AppendRegisteredBoneFrame(wristBoneName, wristBf)

	// var wristTwistQuat *mmath.MQuaternion
	// wristKey := math.MaxFloat64
	// for j := range loopLimit {
	// 	// IKありの変化量を取得
	// 	wristIkOnDeltas = armIkMotion.AnimateBoneContinueIk(fno, wristTwistIkModel,
	// 		[]string{wristBoneName, middleTailBoneName, thumbZBoneName, wristTwistBoneName, wristTwistIkBoneName}, true)

	// 	wristTwistOnDelta := wristIkOnDeltas.Get(wristTwistBoneName, fno)
	// 	middleOnDelta := wristIkOnDeltas.Get(middleTailBoneName, fno)
	// 	thumbZOnDelta := wristIkOnDeltas.Get(thumbZBoneName, fno)
	// 	middleDistance := middleOnDelta.Position.Distance(middleTailOffDelta.Position)
	// 	thumbZDistance := thumbZOnDelta.Position.Distance(thumbZOffDelta.Position)

	// 	keySum := middleDistance + thumbZDistance
	// 	mlog.V("[Wrist] Distance [%d][%s][%d] middle: %f, thumbZ: %f, keySum: %f, armKey: %f",
	// 		fno, direction, j, middleDistance, thumbZDistance, keySum, wristKey)

	// 	if keySum < wristKey {
	// 		wristKey = keySum
	// 		wristTwistQuat = wristTwistOnDelta.FrameRotationWithoutEffect

	// 		mlog.V("[Wrist] Update IK [%d][%s][%d] middle: %f, thumbZ: %f, keySum: %f, armKey: %f",
	// 			fno, direction, j, middleDistance, thumbZDistance, keySum, wristKey)
	// 	}

	// 	if middleDistance < 1e-2 && thumbZDistance < 0.1 {
	// 		mlog.V("*** [Wrist] Converged at [%d][%s][%d] middle: %f, thumbZ: %f, keySum: %f, armKey: %f",
	// 			fno, direction, j, middleDistance, thumbZDistance, keySum, wristKey)
	// 		break
	// 	}
	// }

	// // 最も近いものを採用
	// mlog.V("[Wrist] FIX Converged at [%d][%s] distance: %f", fno, direction, wristKey)

	// // FKの各キーフレに値を設定
	// wristTwistBf := vmd.NewBoneFrame(fno)
	// wristTwistBf.Rotation.SetQuaternion(wristTwistQuat)
	// armIkMotion.AppendRegisteredBoneFrame(wristTwistBoneName, wristTwistBf)

	// if mlog.IsIkVerbose() {
	// 	armIkMotion.Path = strings.Replace(prevMotion.Path, "heel.vmd", direction+"_arm_ik_2.vmd", -1)
	// 	err := vmd.Write(armIkMotion)
	// 	if err != nil {
	// 		mlog.E("Failed to write arm ik vmd: %v", err)
	// 	}
	// }
}

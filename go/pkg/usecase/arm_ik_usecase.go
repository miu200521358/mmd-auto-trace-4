package usecase

import (
	"fmt"
	"math"
	"path/filepath"
	"strings"
	"time"

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
	mlog.SetLevel(mlog.IK_VERBOSE)

	armBoneName := pmx.ARM.StringFromDirection(direction)
	elbowBoneName := pmx.ELBOW.StringFromDirection(direction)
	wristBoneName := pmx.WRIST.StringFromDirection(direction)
	armTwistBoneName := pmx.ARM_TWIST.StringFromDirection(direction)
	armTwistIkBoneName := fmt.Sprintf("%s腕捩ＩＫ", direction)

	// IKなしの変化量を取得
	armIkOffDeltas := prevMotion.BoneFrames.Deform(fno, armTwistIkModel,
		[]string{armBoneName, elbowBoneName, wristBoneName, armTwistBoneName, armTwistIkBoneName}, false, true, false, nil)

	// 腕IK --------------------

	// 腕捩ＩＫは手首の位置を基準とする
	armTwistIkBf := vmd.NewBoneFrame(fno)
	wristOffDelta := armIkOffDeltas.GetByName(wristBoneName)
	armTwistIkBf.Position = wristOffDelta.GlobalPosition().Subed(
		armTwistIkModel.Bones.GetByName(armTwistIkBoneName).Position)
	armIkMotion.AppendBoneFrame(armTwistIkBoneName, armTwistIkBf)

	// middleTailOffDelta := armIkOffDeltas.Get(middleTailBoneName, fno)

	// 腕の捩りを除去する
	armOffDelta := armIkOffDeltas.GetByName(armBoneName)
	armXQuat, armYZQuat := armOffDelta.GlobalRotation().SeparateTwistByAxis(
		armTwistIkModel.Bones.GetByName(armBoneName).NormalizedLocalAxisX)
	armBf := vmd.NewBoneFrame(fno)
	armBf.Rotation = mmath.NewRotationByQuaternion(armYZQuat)
	armIkMotion.AppendRegisteredBoneFrame(armBoneName, armBf)

	// ひじをローカルY軸に対して曲げる
	elbowOffDelta := armIkOffDeltas.GetByName(elbowBoneName)
	_, elbowYZQuat := elbowOffDelta.GlobalRotation().SeparateTwistByAxis(
		armTwistIkModel.Bones.GetByName(elbowBoneName).NormalizedLocalAxisX)
	elbowBf := vmd.NewBoneFrame(fno)
	elbowQuat := mmath.NewMQuaternionFromAxisAngles(
		armTwistIkModel.Bones.GetByName(elbowBoneName).NormalizedLocalAxisY, elbowYZQuat.ToRadian())
	elbowBf.Rotation = mmath.NewRotationByQuaternion(elbowQuat)
	armIkMotion.AppendRegisteredBoneFrame(elbowBoneName, elbowBf)

	if mlog.IsIkVerbose() {
		dirPath := fmt.Sprintf("%s/IK_step", filepath.Dir(armTwistIkModel.Path))

		{
			date := time.Now().Format("20060102_150405")
			ikMotionPath := fmt.Sprintf("%s/%04d_%s_%s_X.vmd", dirPath, 1, date, armTwistBoneName)
			motion := vmd.NewVmdMotion(ikMotionPath)

			bf := vmd.NewBoneFrame(1)
			bf.Rotation.SetQuaternion(armXQuat)
			motion.AppendRegisteredBoneFrame(armBoneName, bf)
			vmd.Write(motion)
		}
		{
			date := time.Now().Format("20060102_150405")
			ikMotionPath := fmt.Sprintf("%s/%04d_%s_%s.vmd", dirPath, 1, date, armTwistBoneName)
			ikMotion := vmd.NewVmdMotion(ikMotionPath)

			{
				bf := armBf.Copy().(*vmd.BoneFrame)
				bf.Index = 1
				ikMotion.AppendRegisteredBoneFrame(armBoneName, bf)
			}
			{
				bf := elbowBf.Copy().(*vmd.BoneFrame)
				bf.Index = 1
				ikMotion.AppendRegisteredBoneFrame(elbowBoneName, bf)
			}

			vmd.Write(ikMotion)
		}
	}

	var armIkOnDeltas *vmd.BoneDeltas
	var armTwistQuat *mmath.MQuaternion
	armKey := math.MaxFloat64
	for j := range loopLimit {
		// IKありの変化量を取得
		armIkOnDeltas = armIkMotion.BoneFrames.Deform(fno, armTwistIkModel,
			[]string{armBoneName, elbowBoneName, wristBoneName, armTwistBoneName, armTwistIkBoneName}, true, true, false, nil)

		armTwistOnDelta := armIkOnDeltas.GetByName(armTwistBoneName)
		elbowOnDelta := armIkOnDeltas.GetByName(elbowBoneName)
		wristOnDelta := armIkOnDeltas.GetByName(wristBoneName)
		elbowDistance := elbowOnDelta.GlobalPosition().Distance(elbowOffDelta.GlobalPosition())
		wristDistance := wristOnDelta.GlobalPosition().Distance(wristOffDelta.GlobalPosition())

		keySum := elbowDistance + wristDistance

		// 腕捩りは初期値として設定する
		armTwistBf := vmd.NewBoneFrame(fno)
		armTwistBf.Rotation.SetQuaternion(armTwistOnDelta.GlobalRotation())
		armIkMotion.AppendRegisteredBoneFrame(armTwistBoneName, armTwistBf)

		mlog.V("[Arm] Distance [%d][%s][%d] elbow: %f, wrist: %f, keySum: %f, armKey: %f, armTwist: %v",
			fno, direction, j, elbowDistance, wristDistance, keySum, armKey, armTwistBf.Rotation.GetDegreesMMD())

		if keySum < armKey {
			armKey = keySum
			armTwistQuat = armTwistOnDelta.GlobalRotation()

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

}

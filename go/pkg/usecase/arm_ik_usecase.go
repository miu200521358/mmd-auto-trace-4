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
	mlog.D("[%d/%d] Convert Arm Ik ...", motionNum, allNum)

	pr := &pmx.PmxReader{}

	// 腕捩IK用モデルを読み込み
	armIkData, err := pr.ReadByFilepath(strings.Replace(modelPath, ".pmx", "_arm_ik.pmx", -1))
	if err != nil {
		mlog.E("Failed to read pmx: %v", err)
	}
	armIkModel := armIkData.(*pmx.PmxModel)

	minFrame := prevMotion.BoneFrames.Get(pmx.CENTER.String()).GetMinFrame()
	maxFrame := prevMotion.BoneFrames.Get(pmx.CENTER.String()).GetMaxFrame()

	bar := utils.NewProgressBar(maxFrame - minFrame)

	armIkMotion := prevMotion.Copy().(*vmd.VmdMotion)

	for fno := minFrame; fno <= maxFrame; fno++ {
		bar.Increment()

		convertArmIkMotion(prevMotion, armIkMotion, "右", fno, armIkModel)
		convertArmIkMotion(prevMotion, armIkMotion, "左", fno, armIkModel)
	}

	armIkMotion.BoneFrames.Delete("左腕ＩＫ")
	armIkMotion.BoneFrames.Delete("左腕捩ＩＫ")
	armIkMotion.BoneFrames.Delete("右腕ＩＫ")
	armIkMotion.BoneFrames.Delete("右腕捩ＩＫ")

	bar.Finish()

	return armIkMotion
}

func convertArmIkMotion(
	prevMotion, armIkMotion *vmd.VmdMotion, direction string, fno int, armIkModel *pmx.PmxModel,
) {
	armBoneName := pmx.ARM.StringFromDirection(direction)
	elbowBoneName := pmx.ELBOW.StringFromDirection(direction)
	wristBoneName := pmx.WRIST.StringFromDirection(direction)
	armTwistBoneName := pmx.ARM_TWIST.StringFromDirection(direction)
	armIkBoneName := fmt.Sprintf("%s腕ＩＫ", direction)
	armTwistIkBoneName := fmt.Sprintf("%s腕捩ＩＫ", direction)

	loopLimit := 500

	// IKなしの変化量を取得
	armIkOffDeltas := prevMotion.BoneFrames.Deform(fno, armIkModel,
		[]string{armBoneName, elbowBoneName, wristBoneName, armTwistBoneName, armIkBoneName, armTwistIkBoneName}, false, nil)

	// 腕IK --------------------

	armOffDelta := armIkOffDeltas.GetByName(armBoneName)
	elbowOffDelta := armIkOffDeltas.GetByName(elbowBoneName)
	wristOffDelta := armIkOffDeltas.GetByName(wristBoneName)

	{
		// 腕捩ＩＫは手首の位置を基準とする
		armTwistIkBf := vmd.NewBoneFrame(fno)
		armTwistIkBf.Position = wristOffDelta.GlobalPosition().Subed(armIkModel.Bones.GetByName(armTwistIkBoneName).Position)
		armIkMotion.AppendBoneFrame(armTwistIkBoneName, armTwistIkBf)

		// 腕ＩＫはひじの位置を基準とする
		armIkBf := vmd.NewBoneFrame(fno)
		armIkBf.Position = elbowOffDelta.GlobalPosition().Subed(armTwistIkBf.Position).Subed(armIkModel.Bones.GetByName(armIkBoneName).Position)
		armIkMotion.AppendBoneFrame(armIkBoneName, armIkBf)
	}

	{
		// 腕の捩りを除去する
		_, armYZQuat := armOffDelta.GlobalRotation().SeparateTwistByAxis(armIkModel.Bones.GetByName(armBoneName).NormalizedLocalAxisX)
		armBf := vmd.NewBoneFrame(fno)
		armBf.Rotation = armYZQuat
		armIkMotion.AppendRegisteredBoneFrame(armBoneName, armBf)

		// ひじをローカルY軸に対して曲げる
		_, elbowYZQuat := elbowOffDelta.GlobalRotation().SeparateTwistByAxis(armIkModel.Bones.GetByName(elbowBoneName).NormalizedLocalAxisX)
		elbowBf := vmd.NewBoneFrame(fno)
		elbowQuat := mmath.NewMQuaternionFromAxisAngles(
			armIkModel.Bones.GetByName(elbowBoneName).NormalizedLocalAxisY, elbowYZQuat.ToRadian())
		elbowBf.Rotation = elbowQuat
		armIkMotion.AppendRegisteredBoneFrame(elbowBoneName, elbowBf)
	}

	// if mlog.DsIkVerbose() {
	// 	dirPath := fmt.Sprintf("%s/IK_step", filepath.Dir(armIkModel.Path))

	// 	{
	// 		date := time.Now().Format("20060102_150405")
	// 		ikMotionPath := fmt.Sprintf("%s/%04d_%s_%s_X.vmd", dirPath, 1, date, armTwistBoneName)
	// 		motion := vmd.NewVmdMotion(ikMotionPath)

	// 		bf := vmd.NewBoneFrame(1)
	// 		bf.Rotation.SetQuaternion(armXQuat)
	// 		motion.AppendRegisteredBoneFrame(armBoneName, bf)
	// 		vmd.Write(motion)
	// 	}
	// 	{
	// 		date := time.Now().Format("20060102_150405")
	// 		ikMotionPath := fmt.Sprintf("%s/%04d_%s_%s.vmd", dirPath, 1, date, armTwistBoneName)
	// 		ikMotion := vmd.NewVmdMotion(ikMotionPath)

	// 		{
	// 			bf := armBf.Copy().(*vmd.BoneFrame)
	// 			bf.Index = 1
	// 			ikMotion.AppendRegisteredBoneFrame(armBoneName, bf)
	// 		}
	// 		{
	// 			bf := elbowBf.Copy().(*vmd.BoneFrame)
	// 			bf.Index = 1
	// 			ikMotion.AppendRegisteredBoneFrame(elbowBoneName, bf)
	// 		}

	// 		vmd.Write(ikMotion)
	// 	}
	// }

	var armIkOnDeltas *vmd.BoneDeltas
	var armQuat *mmath.MQuaternion
	var armTwistQuat *mmath.MQuaternion
	elbowMinDistance := math.MaxFloat64
	wristMinDistance := math.MaxFloat64
	for j := range loopLimit {
		// IKありの変化量を取得
		armIkOnDeltas = armIkMotion.BoneFrames.Deform(fno, armIkModel,
			[]string{armBoneName, elbowBoneName, wristBoneName, armTwistBoneName, armIkBoneName, armTwistIkBoneName}, true, nil)

		armOnDelta := armIkOnDeltas.GetByName(armBoneName)
		armTwistOnDelta := armIkOnDeltas.GetByName(armTwistBoneName)
		elbowOnDelta := armIkOnDeltas.GetByName(elbowBoneName)
		wristOnDelta := armIkOnDeltas.GetByName(wristBoneName)
		elbowDistance := elbowOnDelta.GlobalPosition().Distance(elbowOffDelta.GlobalPosition())
		wristDistance := wristOnDelta.GlobalPosition().Distance(wristOffDelta.GlobalPosition())

		// 腕を初期値として設定する
		armBf := vmd.NewBoneFrame(fno)
		armBf.Rotation = armOnDelta.GlobalRotation()
		armIkMotion.AppendRegisteredBoneFrame(armBoneName, armBf)

		// 腕捩りは初期値として設定する
		armTwistBf := vmd.NewBoneFrame(fno)
		armTwistBf.Rotation = armTwistOnDelta.GlobalRotation()
		armIkMotion.AppendRegisteredBoneFrame(armTwistBoneName, armTwistBf)

		mlog.V("[Arm] Distance [%d][%s][%d] elbow: %f, wrist: %f, armTwist: %v",
			fno, direction, j, elbowDistance, wristDistance, armTwistBf.Rotation.ToMMDDegrees())

		if (elbowDistance <= elbowMinDistance && wristDistance <= wristMinDistance+0.01) ||
			(elbowDistance <= elbowMinDistance+0.01 && wristDistance <= wristMinDistance) {

			elbowMinDistance = elbowDistance
			wristMinDistance = wristDistance
			armQuat = armOnDelta.GlobalRotation()
			armTwistQuat = armTwistOnDelta.GlobalRotation()

			mlog.V("[Arm] Update IK [%d][%s][%d] elbow: %f, wrist: %f", fno, direction, j, elbowDistance, wristDistance)
		}

		if elbowDistance < 0.01 && wristDistance < 0.01 {
			mlog.V("*** [Arm] Converged at [%d][%s][%d] elbow: %f, wrist: %f", fno, direction, j, elbowDistance, wristDistance)
			break
		}
	}

	// 最も近いものを採用
	mlog.V("[Arm] FIX Converged at [%d][%s] distance: %f", fno, direction, elbowMinDistance)

	// FKの各キーフレに値を設定
	armBf := vmd.NewBoneFrame(fno)
	armBf.Rotation = armQuat
	armIkMotion.AppendRegisteredBoneFrame(armBoneName, armBf)

	armTwistBf := vmd.NewBoneFrame(fno)
	armTwistBf.Rotation = armTwistQuat
	armIkMotion.AppendRegisteredBoneFrame(armTwistBoneName, armTwistBf)

	if elbowMinDistance > 0.3 || wristMinDistance > 0.3 {
		mlog.D("xxx [Arm] NO FIX Converged at [%d][%s] elbow: %f, wrist: %f", fno, direction, elbowMinDistance, wristMinDistance)

		// 差が大きい場合、キーフレを削除する
		armIkMotion.BoneFrames.Get(armBoneName).Delete(fno)
		armIkMotion.BoneFrames.Get(armTwistBoneName).Delete(fno)
	}

}

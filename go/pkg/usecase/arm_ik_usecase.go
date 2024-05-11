package usecase

import (
	"fmt"
	"math"
	"strings"
	"sync"

	"github.com/miu200521358/mlib_go/pkg/deform"
	"github.com/miu200521358/mlib_go/pkg/mmath"
	"github.com/miu200521358/mlib_go/pkg/mutils/mlog"
	"github.com/miu200521358/mlib_go/pkg/pmx"
	"github.com/miu200521358/mlib_go/pkg/vmd"
)

func ConvertArmIk(allPrevMotions []*vmd.VmdMotion, modelPath string) []*vmd.VmdMotion {
	mlog.I("Start: Arm Ik =============================")

	allArmIkMotions := make([]*vmd.VmdMotion, len(allPrevMotions))

	// mlog.SetLevel(mlog.IK_VERBOSE)

	// 全体のタスク数をカウント
	totalFrames := len(allPrevMotions)
	for _, prevMotion := range allPrevMotions {
		totalFrames += int(prevMotion.BoneFrames.GetItem(pmx.CENTER.String()).GetMaxFrame() - prevMotion.BoneFrames.GetItem(pmx.CENTER.String()).GetMinFrame() + 1.0)
	}

	pr := &pmx.PmxReader{}

	// 腕捩IK用モデルを読み込み
	armTwistIkData, err := pr.ReadByFilepath(strings.Replace(modelPath, ".pmx", "_arm_twist_ik.pmx", -1))
	if err != nil {
		mlog.E("Failed to read pmx: %v", err)
	}
	armTwistIkModel := armTwistIkData.(*pmx.PmxModel)
	armTwistIkModel.SetUp()

	// 手捩IK用モデルを読み込み
	wristTwistIkData, err := pr.ReadByFilepath(strings.Replace(modelPath, ".pmx", "_wrist_twist_ik.pmx", -1))
	if err != nil {
		mlog.E("Failed to read pmx: %v", err)
	}
	wristTwistIkModel := wristTwistIkData.(*pmx.PmxModel)
	wristTwistIkModel.SetUp()

	bar := newProgressBar(totalFrames)

	// Create a WaitGroup
	var wg sync.WaitGroup

	loopLimit := 100

	// Iterate over allRotateMotions in parallel
	for i, prevMotion := range allPrevMotions {
		// Increment the WaitGroup counter
		wg.Add(1)

		go func(i int, prevMotion *vmd.VmdMotion) {
			defer wg.Done()
			defer mlog.I("[%d/%d] Convert Arm Ik ...", i, len(allPrevMotions))

			armIkMotion := prevMotion.Copy().(*vmd.VmdMotion)
			armIkMotion.Path = strings.Replace(prevMotion.Path, "_leg_ik.vmd", "_arm_ik.vmd", -1)
			armIkMotion.SetName(fmt.Sprintf("MAT4 ArmIk %02d", i+1))

			for fno := prevMotion.BoneFrames.GetItem(pmx.CENTER.String()).GetMinFrame(); fno <= prevMotion.BoneFrames.GetItem(pmx.CENTER.String()).GetMaxFrame(); fno += 1.0 {
				bar.Increment()

				var wg sync.WaitGroup
				errChan := make(chan error, 2) // エラーを受け取るためのチャネル

				calcIk := func(prevMotion *vmd.VmdMotion, armIkMotion *vmd.VmdMotion, direction string) {
					defer wg.Done()

					convertArmIkMotion(prevMotion, armIkMotion, direction, fno, armTwistIkModel, wristTwistIkModel, loopLimit)
				}

				wg.Add(2) // 2つのゴルーチンを待つ

				go calcIk(prevMotion, armIkMotion, "右")
				go calcIk(prevMotion, armIkMotion, "左")

				wg.Wait()      // すべてのゴルーチンが完了するのを待つ
				close(errChan) // チャネルを閉じる

				// エラーがあれば出力
				for err := range errChan {
					mlog.E(err.Error())
				}
			}

			armIkMotion.BoneFrames.Delete("左腕捩ＩＫ")
			armIkMotion.BoneFrames.Delete("左手捩ＩＫ")
			armIkMotion.BoneFrames.Delete("右腕捩ＩＫ")
			armIkMotion.BoneFrames.Delete("右手捩ＩＫ")

			armIkMotion.Path = strings.Replace(prevMotion.Path, "_heel.vmd", "_arm_ik.vmd", -1)
			armIkMotion.SetName(fmt.Sprintf("MAT4 ArmIk %02d", i+1))
			err := vmd.Write(armIkMotion)
			if err != nil {
				mlog.E("Failed to write arm ik vmd: %v", err)
			}

			allArmIkMotions[i] = armIkMotion
		}(i, prevMotion)
	}

	wg.Wait()
	bar.Finish()

	mlog.I("End: Arm Ik =============================")

	return allArmIkMotions
}

func convertArmIkMotion(
	prevMotion *vmd.VmdMotion, armIkMotion *vmd.VmdMotion, direction string, fno float32,
	armTwistIkModel *pmx.PmxModel, wristTwistIkModel *pmx.PmxModel, loopLimit int,
) {

	armBoneName := pmx.ARM.StringFromDirection(direction)
	elbowBoneName := pmx.ELBOW.StringFromDirection(direction)
	wristBoneName := pmx.WRIST.StringFromDirection(direction)
	middleTailBoneName := pmx.MIDDLE_TAIL.StringFromDirection(direction)
	armTwistBoneName := pmx.ARM_TWIST.StringFromDirection(direction)
	wristTwistBoneName := pmx.WRIST_TWIST.StringFromDirection(direction)
	armTwistIkBoneName := fmt.Sprintf("%s腕捩ＩＫ", direction)
	wristTwistIkBoneName := fmt.Sprintf("%s手捩ＩＫ", direction)
	thumbZBoneName := fmt.Sprintf("%s親指Z垂線", direction)

	// IKなしの変化量を取得
	armIkOffDeltas := prevMotion.AnimateBone(fno, armTwistIkModel,
		[]string{armBoneName, elbowBoneName, wristBoneName, middleTailBoneName, thumbZBoneName,
			armTwistBoneName, wristTwistBoneName, armTwistIkBoneName}, false)

	// 腕IK --------------------

	// 腕捩ＩＫは手首の位置を基準とする
	armTwistIkBf := deform.NewBoneFrame(fno)
	wristOffDelta := armIkOffDeltas.GetItem(wristBoneName, fno)
	armTwistIkBf.Position = wristOffDelta.Position.Subed(
		armTwistIkModel.Bones.GetItemByName(armTwistIkBoneName).Position)
	armIkMotion.AppendBoneFrame(armTwistIkBoneName, armTwistIkBf)

	middleTailOffDelta := armIkOffDeltas.GetItem(middleTailBoneName, fno)

	// 腕の捩りを除去する
	armOffDelta := armIkOffDeltas.GetItem(armBoneName, fno)
	_, _, _, armYZQuat := armOffDelta.FrameRotation.SeparateByAxis(
		armTwistIkModel.Bones.GetItemByName(armBoneName).NormalizedLocalAxisX)
	armBf := deform.NewBoneFrame(fno)
	armBf.Rotation.SetQuaternion(armYZQuat)
	armIkMotion.AppendRegisteredBoneFrame(armBoneName, armBf)

	// ひじをローカルY軸に対して曲げる
	elbowOffDelta := armIkOffDeltas.GetItem(elbowBoneName, fno)
	_, _, _, elbowYZQuat := elbowOffDelta.FrameRotation.SeparateByAxis(
		armTwistIkModel.Bones.GetItemByName(elbowBoneName).NormalizedLocalAxisX)
	elbowBf := deform.NewBoneFrame(fno)
	elbowBf.Rotation.SetQuaternion(mmath.NewMQuaternionFromAxisAngles(
		armTwistIkModel.Bones.GetItemByName(elbowBoneName).NormalizedLocalAxisY, elbowYZQuat.ToRadian()))
	armIkMotion.AppendRegisteredBoneFrame(elbowBoneName, elbowBf)

	if mlog.IsIkVerbose() {
		armIkMotion.Path = strings.Replace(prevMotion.Path, "leg_ik.vmd", direction+"_arm_ik_0.vmd", -1)
		err := vmd.Write(armIkMotion)
		if err != nil {
			mlog.E("Failed to write arm ik vmd: %v", err)
		}
	}

	var wristIkOnDeltas *deform.BoneDeltas
	var armTwistQuat *mmath.MQuaternion
	armKey := math.MaxFloat64
	for j := range loopLimit {
		// IKありの変化量を取得
		wristIkOnDeltas = armIkMotion.AnimateBone(fno, armTwistIkModel,
			[]string{armBoneName, elbowBoneName, wristBoneName, middleTailBoneName, thumbZBoneName,
				armTwistBoneName, wristTwistBoneName, armTwistIkBoneName}, true)

		armTwistOnDelta := wristIkOnDeltas.GetItem(armTwistBoneName, fno)
		elbowOnDelta := wristIkOnDeltas.GetItem(elbowBoneName, fno)
		wristOnDelta := wristIkOnDeltas.GetItem(wristBoneName, fno)
		elbowDistance := elbowOnDelta.Position.Distance(elbowOffDelta.Position)
		wristDistance := wristOnDelta.Position.Distance(wristOffDelta.Position)

		keySum := elbowDistance + wristDistance
		mlog.V("[Arm] Distance [%d][%s][%d] elbow: %f, wrist: %f, keySum: %f, armKey: %f",
			int(fno), direction, j, elbowDistance, wristDistance, keySum, armKey)

		if keySum < armKey {
			armKey = keySum
			armTwistQuat = armTwistOnDelta.FrameRotationWithoutEffect

			mlog.V("[Arm] Update IK [%d][%s][%d] elbow: %f, wrist: %f, keySum: %f, armKey: %f",
				int(fno), direction, j, elbowDistance, wristDistance, keySum, armKey)
		}

		if elbowDistance < 1e-2 && wristDistance < 1e-2 {
			mlog.V("*** [Arm] Converged at [%d][%s][%d] elbow: %f, wrist: %f, keySum: %f, armKey: %f",
				int(fno), direction, j, elbowDistance, wristDistance, keySum, armKey)
			break
		}
	}

	// 最も近いものを採用
	mlog.V("[Arm] FIX Converged at [%d][%s] distance: %f", int(fno), direction, armKey)

	// FKの各キーフレに値を設定
	armTwistBf := deform.NewBoneFrame(fno)
	armTwistBf.Rotation.SetQuaternion(armTwistQuat)
	armIkMotion.AppendRegisteredBoneFrame(armTwistBoneName, armTwistBf)

	if mlog.IsIkVerbose() {
		armIkMotion.Path = strings.Replace(prevMotion.Path, "leg_ik.vmd", direction+"_arm_ik_1.vmd", -1)
		err := vmd.Write(armIkMotion)
		if err != nil {
			mlog.E("Failed to write arm ik vmd: %v", err)
		}
	}

	// 手捩IK --------------------

	// 手捩IKは親指Z垂線の位置を基準とする
	wristTwistIkBf := deform.NewBoneFrame(fno)
	thumbZOffDelta := armIkOffDeltas.GetItem(thumbZBoneName, fno)
	wristTwistIkBf.Position = thumbZOffDelta.Position.Subed(
		wristTwistIkModel.Bones.GetItemByName(wristTwistIkBoneName).Position)
	armIkMotion.AppendBoneFrame(wristTwistIkBoneName, wristTwistIkBf)

	// 手首の捩りを除去する
	_, _, _, wristYZQuat := wristOffDelta.FrameRotation.SeparateByAxis(
		armTwistIkModel.Bones.GetItemByName(wristBoneName).NormalizedLocalAxisX)
	wristBf := deform.NewBoneFrame(fno)
	wristBf.Rotation.SetQuaternion(wristYZQuat)
	armIkMotion.AppendRegisteredBoneFrame(wristBoneName, wristBf)

	var wristTwistQuat *mmath.MQuaternion
	wristKey := math.MaxFloat64
	for j := range loopLimit {
		// IKありの変化量を取得
		wristIkOnDeltas = armIkMotion.AnimateBone(fno, wristTwistIkModel,
			[]string{wristBoneName, middleTailBoneName, thumbZBoneName, wristTwistBoneName, wristTwistIkBoneName}, true)

		wristTwistOnDelta := wristIkOnDeltas.GetItem(wristTwistBoneName, fno)
		middleOnDelta := wristIkOnDeltas.GetItem(middleTailBoneName, fno)
		thumbZOnDelta := wristIkOnDeltas.GetItem(thumbZBoneName, fno)
		middleDistance := middleOnDelta.Position.Distance(middleTailOffDelta.Position)
		thumbZDistance := thumbZOnDelta.Position.Distance(thumbZOffDelta.Position)

		keySum := middleDistance + thumbZDistance
		mlog.V("[Wrist] Distance [%d][%s][%d] middle: %f, thumbZ: %f, keySum: %f, armKey: %f",
			int(fno), direction, j, middleDistance, thumbZDistance, keySum, wristKey)

		if keySum < wristKey {
			wristKey = keySum
			wristTwistQuat = wristTwistOnDelta.FrameRotationWithoutEffect

			mlog.V("[Wrist] Update IK [%d][%s][%d] middle: %f, thumbZ: %f, keySum: %f, armKey: %f",
				int(fno), direction, j, middleDistance, thumbZDistance, keySum, wristKey)
		}

		if middleDistance < 1e-2 && thumbZDistance < 0.1 {
			mlog.V("*** [Wrist] Converged at [%d][%s][%d] middle: %f, thumbZ: %f, keySum: %f, armKey: %f",
				int(fno), direction, j, middleDistance, thumbZDistance, keySum, wristKey)
			break
		}
	}

	// 最も近いものを採用
	mlog.V("[Wrist] FIX Converged at [%d][%s] distance: %f", int(fno), direction, wristKey)

	// FKの各キーフレに値を設定
	wristTwistBf := deform.NewBoneFrame(fno)
	wristTwistBf.Rotation.SetQuaternion(wristTwistQuat)
	armIkMotion.AppendRegisteredBoneFrame(wristTwistBoneName, wristTwistBf)

	if mlog.IsIkVerbose() {
		armIkMotion.Path = strings.Replace(prevMotion.Path, "leg_ik.vmd", direction+"_arm_ik_2.vmd", -1)
		err := vmd.Write(armIkMotion)
		if err != nil {
			mlog.E("Failed to write arm ik vmd: %v", err)
		}
	}
}

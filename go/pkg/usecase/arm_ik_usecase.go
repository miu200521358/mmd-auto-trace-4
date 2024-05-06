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
	allArmIkMotions := make([]*vmd.VmdMotion, len(allPrevMotions))

	// mlog.SetLevel(mlog.IK_VERBOSE)

	// 全体のタスク数をカウント
	totalFrames := len(allPrevMotions)
	for _, prevMotion := range allPrevMotions {
		totalFrames += int(prevMotion.BoneFrames.GetItem("センター").GetMaxFrame() - prevMotion.BoneFrames.GetItem("センター").GetMinFrame() + 1.0)
	}

	pr := &pmx.PmxReader{}

	// 腕IK用(末端小指)モデルを読み込み
	armIkData, err := pr.ReadByFilepath(strings.Replace(modelPath, ".pmx", "_arm_ik.pmx", -1))
	if err != nil {
		mlog.E("Failed to read pmx: %v", err)
	}
	armIkModel := armIkData.(*pmx.PmxModel)
	armIkModel.SetUp()

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

			armIkMotion := prevMotion.Copy().(*vmd.VmdMotion)
			armIkMotion.Path = strings.Replace(prevMotion.Path, "_leg_ik.vmd", "_arm_ik.vmd", -1)
			armIkMotion.SetName(fmt.Sprintf("MAT4 ArmIk %02d", i+1))

			for fno := prevMotion.BoneFrames.GetItem("センター").GetMinFrame(); fno <= prevMotion.BoneFrames.GetItem("センター").GetMaxFrame(); fno += 1.0 {
				bar.Increment()

				var wg sync.WaitGroup
				errChan := make(chan error, 2) // エラーを受け取るためのチャネル

				calcIk := func(prevMotion *vmd.VmdMotion, armIkMotion *vmd.VmdMotion, direction string) {
					defer wg.Done()

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
					armIkOffDeltas := prevMotion.AnimateBone(float32(fno), armIkModel,
						[]string{armBoneName, elbowBoneName, wristBoneName, middleTailBoneName, thumbZBoneName,
							armTwistBoneName, wristTwistBoneName, armTwistIkBoneName, wristTwistIkBoneName}, false)

					// 腕IK --------------------

					// 腕捩ＩＫは手首の位置を基準とする
					armTwistIkBf := deform.NewBoneFrame(float32(fno))
					wristOffDelta := armIkOffDeltas.GetItem(wristBoneName, float32(fno))
					armTwistIkBf.Position = wristOffDelta.Position.Subed(armIkModel.Bones.GetItemByName(armTwistIkBoneName).Position)
					armIkMotion.AppendBoneFrame(armTwistIkBoneName, armTwistIkBf)

					// 手捩IKは親指Z垂線の位置を基準とする
					wristTwistIkBf := deform.NewBoneFrame(float32(fno))
					thumbZOffDelta := armIkOffDeltas.GetItem(thumbZBoneName, float32(fno))
					wristTwistIkBf.Position = thumbZOffDelta.Position.Subed(armTwistIkBf.Position).Subed(
						armIkModel.Bones.GetItemByName(wristTwistIkBoneName).Position)
					armIkMotion.AppendBoneFrame(wristTwistIkBoneName, wristTwistIkBf)

					middleTailOffDelta := armIkOffDeltas.GetItem(middleTailBoneName, float32(fno))

					// 腕の捩りを除去する
					armOffDelta := armIkOffDeltas.GetItem(armBoneName, float32(fno))
					_, _, _, armYZQuat := armOffDelta.FrameRotation.SeparateByAxis(
						armIkModel.Bones.GetItemByName(armBoneName).NormalizedLocalAxisX)
					armBf := deform.NewBoneFrame(float32(fno))
					armBf.Rotation.SetQuaternion(armYZQuat)
					armIkMotion.AppendRegisteredBoneFrame(armBoneName, armBf)

					// ひじをローカルY軸に対して曲げる
					elbowOffDelta := armIkOffDeltas.GetItem(elbowBoneName, float32(fno))
					_, _, _, elbowYZQuat := elbowOffDelta.FrameRotation.SeparateByAxis(
						armIkModel.Bones.GetItemByName(elbowBoneName).NormalizedLocalAxisX)
					elbowBf := deform.NewBoneFrame(float32(fno))
					elbowBf.Rotation.SetQuaternion(mmath.NewMQuaternionFromAxisAngles(
						armIkModel.Bones.GetItemByName(elbowBoneName).NormalizedLocalAxisY, elbowYZQuat.ToRadian()))
					armIkMotion.AppendRegisteredBoneFrame(elbowBoneName, elbowBf)

					// 手首の捩りを除去する
					_, _, _, wristYZQuat := wristOffDelta.FrameRotation.SeparateByAxis(
						armIkModel.Bones.GetItemByName(wristBoneName).NormalizedLocalAxisX)
					wristBf := deform.NewBoneFrame(float32(fno))
					wristBf.Rotation.SetQuaternion(wristYZQuat)
					armIkMotion.AppendRegisteredBoneFrame(wristBoneName, wristBf)

					if mlog.IsIkVerbose() {
						armIkMotion.Path = strings.Replace(prevMotion.Path, "leg_ik.vmd", direction+"_arm_ik_0.vmd", -1)
						err := vmd.Write(armIkMotion)
						if err != nil {
							mlog.E("Failed to write arm ik vmd: %v", err)
						}
						bar.Increment()
					}

					var armIkOnDeltas *deform.BoneDeltas
					var armTwistQuat *mmath.MQuaternion
					var wristTwistQuat *mmath.MQuaternion
					var wristQuat *mmath.MQuaternion
					armKey := math.MaxFloat64
					for j := range loopLimit {
						// IKありの変化量を取得
						armIkOnDeltas = armIkMotion.AnimateBone(float32(fno), armIkModel,
							[]string{armBoneName, elbowBoneName, wristBoneName, middleTailBoneName, thumbZBoneName,
								armTwistBoneName, wristTwistBoneName, armTwistIkBoneName, wristTwistIkBoneName}, true)

						armTwistOnDelta := armIkOnDeltas.GetItem(armTwistBoneName, float32(fno))
						elbowOnDelta := armIkOnDeltas.GetItem(elbowBoneName, float32(fno))
						wristTwistOnDelta := armIkOnDeltas.GetItem(wristTwistBoneName, float32(fno))
						wristOnDelta := armIkOnDeltas.GetItem(wristBoneName, float32(fno))
						middleOnDelta := armIkOnDeltas.GetItem(middleTailBoneName, float32(fno))
						thumbZOnDelta := armIkOnDeltas.GetItem(thumbZBoneName, float32(fno))
						elbowDistance := elbowOnDelta.Position.Distance(elbowOffDelta.Position)
						wristDistance := wristOnDelta.Position.Distance(wristOffDelta.Position)
						middleDistance := middleOnDelta.Position.Distance(middleTailOffDelta.Position)
						thumbZDistance := thumbZOnDelta.Position.Distance(thumbZOffDelta.Position)

						keySum := elbowDistance + wristDistance + middleDistance + thumbZDistance
						mlog.V("[Arm] Distance [%d][%s][%d] elbow: %f, wrist: %f, middle: %f, thumbZ: %f, keySum: %f, armKey: %f",
							int(fno), direction, j, elbowDistance, wristDistance, middleDistance, thumbZDistance, keySum, armKey)

						if keySum < armKey {
							armKey = keySum
							armTwistQuat = armTwistOnDelta.FrameRotationWithoutEffect
							wristTwistQuat = wristTwistOnDelta.FrameRotationWithoutEffect
							wristQuat = wristOnDelta.FrameRotationWithoutEffect

							mlog.D("[Arm] Update IK [%d][%s][%d] elbow: %f, wrist: %f, middle: %f, thumbZ: %f, keySum: %f, armKey: %f",
								int(fno), direction, j, elbowDistance, wristDistance, middleDistance, thumbZDistance, keySum, armKey)
						}

						if elbowDistance < 1e-2 && wristDistance < 1e-2 && middleDistance < 0.1 && thumbZDistance < 0.1 {
							mlog.D("*** [Arm] Converged at [%d][%s][%d] elbow: %f, wrist: %f, middle: %f, thumbZ: %f, keySum: %f, armKey: %f",
								int(fno), direction, j, elbowDistance, wristDistance, middleDistance, thumbZDistance, keySum, armKey)
							break
						}
					}

					// 最も近いものを採用
					mlog.D("[Arm] FIX Converged at [%d][%s] distance: %f", int(fno), direction, armKey)

					// FKの各キーフレに値を設定
					armTwistBf := deform.NewBoneFrame(float32(fno))
					armTwistBf.Rotation.SetQuaternion(armTwistQuat)
					armIkMotion.AppendRegisteredBoneFrame(armTwistBoneName, armTwistBf)

					wristTwistBf := deform.NewBoneFrame(float32(fno))
					wristTwistBf.Rotation.SetQuaternion(wristTwistQuat)
					armIkMotion.AppendRegisteredBoneFrame(wristTwistBoneName, wristTwistBf)

					wristBf = deform.NewBoneFrame(float32(fno))
					wristBf.Rotation.SetQuaternion(wristQuat)
					armIkMotion.AppendRegisteredBoneFrame(wristBoneName, wristBf)

					if mlog.IsIkVerbose() {
						armIkMotion.Path = strings.Replace(prevMotion.Path, "leg_ik.vmd", direction+"_arm_ik_1.vmd", -1)
						err := vmd.Write(armIkMotion)
						if err != nil {
							mlog.E("Failed to write arm ik vmd: %v", err)
						}
						bar.Increment()
					}
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

			if mlog.IsDebug() {
				armIkMotion.Path = strings.Replace(prevMotion.Path, "_leg_ik.vmd", "_arm_ik.vmd", -1)
				err := vmd.Write(armIkMotion)
				if err != nil {
					mlog.E("Failed to write arm ik vmd: %v", err)
				}
				bar.Increment()
			}

			armIkMotion.BoneFrames.Delete("左腕捩ＩＫ")
			armIkMotion.BoneFrames.Delete("左手捩ＩＫ")
			armIkMotion.BoneFrames.Delete("右腕捩ＩＫ")
			armIkMotion.BoneFrames.Delete("右手捩ＩＫ")

			allArmIkMotions[i] = armIkMotion
		}(i, prevMotion)
	}

	wg.Wait()
	bar.Finish()

	return allArmIkMotions
}

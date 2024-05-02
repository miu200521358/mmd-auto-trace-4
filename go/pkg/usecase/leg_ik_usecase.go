package usecase

import (
	"fmt"
	"strings"
	"sync"

	"github.com/cheggaaa/pb/v3"
	"github.com/miu200521358/mlib_go/pkg/deform"
	"github.com/miu200521358/mlib_go/pkg/mmath"
	"github.com/miu200521358/mlib_go/pkg/mutils/mlog"
	"github.com/miu200521358/mlib_go/pkg/pmx"
	"github.com/miu200521358/mlib_go/pkg/vmd"
)

func ConvertLegIk(allRotateMotions []*vmd.VmdMotion, modelPath string) []*vmd.VmdMotion {
	allLegIkMotions := make([]*vmd.VmdMotion, len(allRotateMotions))

	mlog.SetLevel(mlog.IK_VERBOSE)

	// 全体のタスク数をカウント
	totalFrames := len(allRotateMotions)
	for _, rotMotion := range allRotateMotions {
		totalFrames += int(rotMotion.GetMaxFrame() - rotMotion.GetMinFrame())
	}

	pr := &pmx.PmxReader{}

	// 足IK用モデルを読み込み
	legIkData, err := pr.ReadByFilepath(strings.Replace(modelPath, ".pmx", "_leg_ik.pmx", -1))
	if err != nil {
		mlog.E("Failed to read pmx: %v", err)
	}
	legIkModel := legIkData.(*pmx.PmxModel)
	legIkModel.SetUp()

	// 足首IK用モデル読み込み
	toeIkData, err := pr.ReadByFilepath(strings.Replace(modelPath, ".pmx", "_toe_ik.pmx", -1))
	if err != nil {
		mlog.E("Failed to read pmx: %v", err)
	}
	toeIkModel := toeIkData.(*pmx.PmxModel)
	toeIkModel.SetUp()

	bar := pb.StartNew(totalFrames)

	// Create a WaitGroup
	var wg sync.WaitGroup

	// Iterate over allRotateMotions in parallel
	for i, rotMotion := range allRotateMotions {
		// Increment the WaitGroup counter
		wg.Add(1)

		go func(i int, rotMotion *vmd.VmdMotion) {
			defer wg.Done()

			legIkMotion := rotMotion.Copy().(*vmd.VmdMotion)
			legIkMotion.Path = strings.Replace(rotMotion.Path, "_rot.vmd", "_leg_ik.vmd", -1)
			legIkMotion.SetName(fmt.Sprintf("MAT4 LegIk %02d", i+1))

			for fno := rotMotion.GetMinFrame(); fno <= rotMotion.GetMaxFrame(); fno += 1.0 {
				bar.Increment()

				var wg sync.WaitGroup
				errChan := make(chan error, 2) // エラーを受け取るためのチャネル

				calcIk := func(rotMotion *vmd.VmdMotion, legIkMotion *vmd.VmdMotion, direction string) {
					defer wg.Done()

					legBoneName := pmx.LEG.StringFromDirection(direction)
					kneeBoneName := pmx.KNEE.StringFromDirection(direction)
					ankleBoneName := pmx.ANKLE.StringFromDirection(direction)
					toeBoneName := pmx.TOE.StringFromDirection(direction)
					legIkBoneName := pmx.LEG_IK.StringFromDirection(direction)
					toeIkBoneName := pmx.TOE_IK.StringFromDirection(direction)
					hipTwistBoneName := fmt.Sprintf("%s足捩", direction)
					ankleVBoneName := fmt.Sprintf("%s足首Z垂線", direction)
					toeSmallBoneName := fmt.Sprintf("%sつま先子", direction)
					heelBoneName := fmt.Sprintf("%sかかと", direction)
					hipIkBoneName := fmt.Sprintf("%sももＩＫ", direction)
					kneeIkBoneName := fmt.Sprintf("%sひざＩＫ", direction)
					ankleIkBoneName := fmt.Sprintf("%s足首ＩＫ", direction)
					ankleTwistIkBoneName := fmt.Sprintf("%s足首捩ＩＫ", direction)

					// IKなしの変化量を取得
					ikOffDeltas := rotMotion.AnimateBone(float32(fno), legIkModel,
						[]string{legBoneName, kneeBoneName, ankleBoneName, ankleVBoneName, toeBoneName,
							toeSmallBoneName, heelBoneName, hipIkBoneName, kneeIkBoneName}, false)

					// 足IK --------------------

					// ももＩＫはひざの位置を基準とする
					hipIkBf := deform.NewBoneFrame(float32(fno))
					kneeOffDelta := ikOffDeltas.GetItem(kneeBoneName, float32(fno))
					hipIkDelta := ikOffDeltas.GetItem(hipIkBoneName, float32(fno))
					hipIkBf.Position = hipIkDelta.GlobalMatrix.Inverted().MulVec3(kneeOffDelta.Position)
					legIkMotion.AppendBoneFrame(hipIkBoneName, hipIkBf)

					// ひざＩＫは足首Z垂線の位置を基準とする
					kneeIkBf := deform.NewBoneFrame(float32(fno))
					ankleVOffDelta := ikOffDeltas.GetItem(ankleVBoneName, float32(fno))
					// ももＩＫが定まった後のひざＩＫ位置を再計算
					kneeIkMat := mmath.NewMMat4()
					kneeIkMat.Translate(kneeOffDelta.Position)
					kneeIkMat.Translate(legIkModel.Bones.GetItemByName(kneeIkBoneName).ParentRelativePosition)
					kneeIkBf.Position = kneeIkMat.Inverted().MulVec3(ankleVOffDelta.Position)
					legIkMotion.AppendBoneFrame(kneeIkBoneName, kneeIkBf)

					// ひざをグローバルX軸に対して曲げる
					_, _, _, kneeYZQuat := kneeOffDelta.FrameRotation.SeparateByAxis(legIkModel.Bones.GetItemByName(kneeBoneName).NormalizedLocalAxisX)
					kneeBf := deform.NewBoneFrame(float32(fno))
					kneeBf.Rotation.SetQuaternion(mmath.NewMQuaternionFromAxisAngles(mmath.MVec3UnitX, -kneeYZQuat.ToRadian()))
					legIkMotion.AppendRegisteredBoneFrame(kneeBoneName, kneeBf)

					for j := range 100 {
						// IKありの変化量を取得
						ikOnDeltas := legIkMotion.AnimateBone(float32(fno), legIkModel,
							[]string{legBoneName, kneeBoneName, ankleBoneName, ankleVBoneName, hipIkBoneName, kneeIkBoneName}, true)

						kneeOnDelta := ikOnDeltas.GetItem(kneeBoneName, float32(fno))
						ankleVOnDelta := ikOnDeltas.GetItem(ankleVBoneName, float32(fno))
						kneeDistance := kneeOnDelta.Position.Distance(kneeOffDelta.Position)
						ankleDistance := ankleVOnDelta.Position.Distance(ankleVOffDelta.Position)

						// 足は足捩りと合成する
						legBf := deform.NewBoneFrame(float32(fno))
						legBf.Rotation.SetQuaternion(
							ikOnDeltas.GetItem(legBoneName, float32(fno)).FrameRotationWithoutEffect.Mul(
								ikOnDeltas.GetItem(hipTwistBoneName, float32(fno)).FrameRotationWithoutEffect),
						)
						legIkMotion.AppendRegisteredBoneFrame(legBoneName, legBf)

						// 足捩りの値はクリア
						hipTwistBf := deform.NewBoneFrame(float32(fno))
						legIkMotion.AppendBoneFrame(hipTwistBoneName, hipTwistBf)

						kneeBf = deform.NewBoneFrame(float32(fno))
						kneeBf.Rotation.SetQuaternion(ikOnDeltas.GetItem(kneeBoneName, float32(fno)).FrameRotationWithoutEffect)
						legIkMotion.AppendRegisteredBoneFrame(kneeBoneName, kneeBf)

						// // 足の捩り成分の大きさをチェック
						// hipTwistXQuat, _, _, _ := legBf.Rotation.GetQuaternion().SeparateByAxis(legIkModel.Bones.GetItemByName(legBoneName).NormalizedLocalAxisX)
						// hipTwistXRad := hipTwistXQuat.ToRadian()
						// mlog.V("Distance at [%d][%s][%d]: knee: %f ankle: %f hipTwist: %f", int(fno), direction, j, kneeDistance, ankleDistance, hipTwistXRad)

						if kneeDistance < 0.3 && ankleDistance < 0.3 {
							mlog.D("[Leg] Converged at [%d][%s][%d] knee: %f ankle: %f", int(fno), direction, j, kneeDistance, ankleDistance)
							break
						}
					}

					// 足ＩＫの位置はIK OFF時の足首位置
					legIkBf := deform.NewBoneFrame(float32(fno))
					ankleOffDelta := ikOffDeltas.GetItem(ankleBoneName, float32(fno))
					legIkBf.Position = ankleOffDelta.Position.Subed(toeIkModel.Bones.GetItemByName(ankleBoneName).Position)

					toeIkOffDeltas := legIkMotion.AnimateBone(float32(fno), toeIkModel, []string{toeIkBoneName}, false)

					// つま先IKの位置はIK OFF時のつま先位置
					toeIkBf := deform.NewBoneFrame(float32(fno))
					toeOffDelta := ikOffDeltas.GetItem(toeBoneName, float32(fno))
					toeIkOffDelta := toeIkOffDeltas.GetItem(toeIkBoneName, float32(fno))
					toeIkBf.Position = toeIkOffDelta.Position.Sub(toeOffDelta.Position)
					legIkMotion.AppendBoneFrame(toeIkBoneName, toeIkBf)

					ikOnDeltas := legIkMotion.AnimateBone(float32(fno), toeIkModel,
						[]string{ankleBoneName, toeBoneName, toeIkBoneName}, true)

					legIkBf.Rotation.SetQuaternion(ikOnDeltas.GetItem(ankleBoneName, float32(fno)).FrameRotationWithoutEffect)
					legIkMotion.AppendRegisteredBoneFrame(legIkBoneName, legIkBf)
				}

				wg.Add(2) // 2つのゴルーチンを待つ

				go calcIk(rotMotion, legIkMotion, "右")
				go calcIk(rotMotion, legIkMotion, "左")

				wg.Wait()      // すべてのゴルーチンが完了するのを待つ
				close(errChan) // チャネルを閉じる

				// エラーがあれば出力
				for err := range errChan {
					mlog.E(err.Error())
				}
			}

			err := vmd.Write(legIkMotion)
			if err != nil {
				mlog.E("Failed to write rotate vmd: %v", err)
			}
			bar.Increment()

			legIkMotion.BoneFrames.Delete("右ももＩＫ")
			legIkMotion.BoneFrames.Delete("右ひざＩＫ")
			legIkMotion.BoneFrames.Delete("右つま先ＩＫ")
			legIkMotion.BoneFrames.Delete("左ももＩＫ")
			legIkMotion.BoneFrames.Delete("左ひざＩＫ")
			legIkMotion.BoneFrames.Delete("左足首ＩＫ")
			legIkMotion.BoneFrames.Delete("左つま先ＩＫ")

			allLegIkMotions[i] = legIkMotion
		}(i, rotMotion)
	}

	wg.Wait()
	bar.Finish()

	return allLegIkMotions
}

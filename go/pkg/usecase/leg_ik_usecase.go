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

func ConvertLegIk(allRotateMotions []*vmd.VmdMotion, ikModelPath string) []*vmd.VmdMotion {
	allLegIkMotions := make([]*vmd.VmdMotion, len(allRotateMotions))

	// mlog.SetLevel(mlog.IK_VERBOSE)

	// 全体のタスク数をカウント
	totalFrames := len(allRotateMotions) * 2

	// 足IK用モデルを読み込み
	pr := &pmx.PmxReader{}
	data, err := pr.ReadByFilepath(ikModelPath)
	if err != nil {
		mlog.E("Failed to read pmx: %v", err)
	}
	legIkModel := data.(*pmx.PmxModel)
	legIkModel.SetUp()

	// つま先IK用モデルを読み込み
	data, err = pr.ReadByFilepath(strings.Replace(ikModelPath, "_leg_ik.pmx", "_toe_ik.pmx", -1))
	if err != nil {
		mlog.E("Failed to read pmx: %v", err)
	}
	toeIkModel := data.(*pmx.PmxModel)
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
			defer bar.Increment()

			legIkMotion := rotMotion.Copy().(*vmd.VmdMotion)
			legIkMotion.Path = strings.Replace(rotMotion.Path, "_rot.vmd", "_leg_ik.vmd", -1)
			legIkMotion.SetName(fmt.Sprintf("MAT4 LegIk %02d", i+1))

			for fno := rotMotion.GetMinFrame(); fno <= rotMotion.GetMaxFrame(); fno += 1.0 {
				var wg sync.WaitGroup
				errChan := make(chan error, 2) // エラーを受け取るためのチャネル

				calcIk := func(rotMotion *vmd.VmdMotion, legIkMotion *vmd.VmdMotion, direction string) {
					defer wg.Done()

					legBoneName := pmx.LEG.StringFromDirection(direction)
					kneeBoneName := pmx.KNEE.StringFromDirection(direction)
					ankleBoneName := pmx.ANKLE.StringFromDirection(direction)
					toeBoneName := pmx.TOE.StringFromDirection(direction)
					legIkBoneName := pmx.LEG_IK.StringFromDirection(direction)
					hipTwistBoneName := fmt.Sprintf("%s足捩", direction)
					toeBigBoneName := fmt.Sprintf("%sつま先親", direction)
					hipIkBoneName := fmt.Sprintf("%sももＩＫ", direction)
					kneeIkBoneName := fmt.Sprintf("%sひざＩＫ", direction)
					ankleIkBoneName := fmt.Sprintf("%s足首ＩＫ", direction)

					// IKなしの変化量を取得
					ikOffDeltas := rotMotion.AnimateBone(float32(fno), legIkModel,
						[]string{legBoneName, kneeBoneName, ankleBoneName, toeBoneName, toeBigBoneName,
							hipIkBoneName, kneeIkBoneName}, false)

					// 足IK --------------------

					// ももＩＫはひざの位置を基準とする
					hipIkBf := deform.NewBoneFrame(float32(fno))
					kneeOffDelta := ikOffDeltas.GetItem(kneeBoneName, float32(fno))
					hipIkDelta := ikOffDeltas.GetItem(hipIkBoneName, float32(fno))
					hipIkBf.Position = hipIkDelta.GlobalMatrix.Inverted().MulVec3(kneeOffDelta.Position)
					legIkMotion.AppendBoneFrame(hipIkBoneName, hipIkBf)

					// ひざＩＫは足首の位置を基準とする
					kneeIkBf := deform.NewBoneFrame(float32(fno))
					ankleOffDelta := ikOffDeltas.GetItem(ankleBoneName, float32(fno))
					// ももＩＫが定まった後のひざＩＫ位置を再計算
					kneeIkMat := mmath.NewMMat4()
					kneeIkMat.Translate(kneeOffDelta.Position)
					kneeIkMat.Translate(legIkModel.Bones.GetItemByName(kneeIkBoneName).ParentRelativePosition)
					kneeIkBf.Position = kneeIkMat.Inverted().MulVec3(ankleOffDelta.Position)
					legIkMotion.AppendBoneFrame(kneeIkBoneName, kneeIkBf)

					// ひざをグローバルX軸に対して曲げる
					_, _, _, kneeYZQuat := kneeOffDelta.FrameRotation.SeparateByAxis(legIkModel.Bones.GetItemByName(kneeBoneName).NormalizedLocalAxisX)
					kneeBf := deform.NewBoneFrame(float32(fno))
					kneeBf.Rotation.SetQuaternion(mmath.NewMQuaternionFromAxisAngles(mmath.MVec3UnitX, -kneeYZQuat.ToRadian()))
					legIkMotion.AppendRegisteredBoneFrame(kneeBoneName, kneeBf)

					for j := range 500 {
						// IKありの変化量を取得
						ikOnDeltas := legIkMotion.AnimateBone(float32(fno), legIkModel,
							[]string{legBoneName, kneeBoneName, ankleBoneName, hipIkBoneName, kneeIkBoneName}, true)

						kneeOnDelta := ikOnDeltas.GetItem(kneeBoneName, float32(fno))
						ankleOnDelta := ikOnDeltas.GetItem(ankleBoneName, float32(fno))
						kneeDistance := kneeOnDelta.Position.Distance(kneeOffDelta.Position)
						ankleDistance := ankleOnDelta.Position.Distance(ankleOffDelta.Position)
						mlog.V("Distance at [%d][%s][%d]: knee: %f ankle: %f", int(fno), direction, j, kneeDistance, ankleDistance)

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

						if kneeDistance < 0.3 && ankleDistance < 0.3 {
							mlog.V("Converged at [%d][%s][%d]", int(fno), direction, j)
							break
						}
					}

					// つま先IK --------------------

					// 足首ＩＫはつま先の位置を基準とする
					ankleIkBf := deform.NewBoneFrame(float32(fno))
					toeDelta := ikOffDeltas.GetItem(toeBoneName, float32(fno))
					// ひざＩＫが定まった後の足首ＩＫ位置を再計算
					ankleIkMat := mmath.NewMMat4()
					ankleIkMat.Translate(ankleOffDelta.Position)
					ankleIkMat.Translate(toeIkModel.Bones.GetItemByName(ankleIkBoneName).ParentRelativePosition)
					ankleIkBf.Position = ankleIkMat.Inverted().MulVec3(toeDelta.Position)
					legIkMotion.AppendBoneFrame(ankleIkBoneName, ankleIkBf)

					// 足首を別途求める
					ikOnDeltas := legIkMotion.AnimateBone(float32(fno), toeIkModel,
						[]string{ankleBoneName, toeBoneName, toeBigBoneName, ankleIkBoneName}, true)
					ankleOnDelta := ikOnDeltas.GetItem(ankleBoneName, float32(fno))

					ankleBf := deform.NewBoneFrame(float32(fno))
					ankleBf.Rotation.SetQuaternion(ankleOnDelta.FrameRotationWithoutEffect)
					legIkMotion.AppendRegisteredBoneFrame(ankleBoneName, ankleBf)

					// 足ＩＫの位置はIK OFF時の足首位置
					legIkBf := deform.NewBoneFrame(float32(fno))
					legIkBf.Rotation.SetQuaternion(ankleOffDelta.LocalMatrix.Quaternion())
					legIkBf.Position = ankleOffDelta.Position.Subed(legIkModel.Bones.GetItemByName(ankleBoneName).Position)
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
			legIkMotion.BoneFrames.Delete("右足首ＩＫ")
			legIkMotion.BoneFrames.Delete("左ももＩＫ")
			legIkMotion.BoneFrames.Delete("左ひざＩＫ")
			legIkMotion.BoneFrames.Delete("左足首ＩＫ")

			allLegIkMotions[i] = legIkMotion
		}(i, rotMotion)
	}

	wg.Wait()
	bar.Finish()

	return allLegIkMotions
}

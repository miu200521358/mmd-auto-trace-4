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

	// mlog.SetLevel(mlog.IK_VERBOSE)

	// 全体のタスク数をカウント
	totalFrames := 0
	for _, rotMotion := range allRotateMotions {
		totalFrames += int(rotMotion.GetMaxFrame()) + 1
	}

	// 足IK用モデルを読み込み
	pr := &pmx.PmxReader{}
	data, err := pr.ReadByFilepath(modelPath)
	if err != nil {
		mlog.E("Failed to read pmx: %v", err)
	}
	model := data.(*pmx.PmxModel)
	model.SetUp()

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
					hipIkBoneName := fmt.Sprintf("%sももＩＫ", direction)
					kneeIkBoneName := fmt.Sprintf("%sひざＩＫ", direction)
					ankleIkBoneName := fmt.Sprintf("%s足首ＩＫ", direction)

					// IKなしの変化量を取得
					ikOffDeltas := rotMotion.AnimateBone(float32(fno), model,
						[]string{legBoneName, kneeBoneName, ankleBoneName, toeBoneName,
							hipIkBoneName, kneeIkBoneName, ankleIkBoneName}, false)

					// ももＩＫはひざの位置を基準とする
					hipIkBf := deform.NewBoneFrame(float32(fno))
					kneeDelta := ikOffDeltas.GetItem(kneeBoneName, float32(fno))
					hipIkDelta := ikOffDeltas.GetItem(hipIkBoneName, float32(fno))
					hipIkBf.Position = hipIkDelta.GlobalMatrix.Inverted().MulVec3(kneeDelta.Position)
					legIkMotion.AppendBoneFrame(hipIkBoneName, hipIkBf)

					// ひざＩＫは足首の位置を基準とする
					kneeIkBf := deform.NewBoneFrame(float32(fno))
					ankleDelta := ikOffDeltas.GetItem(ankleBoneName, float32(fno))
					// ももＩＫが定まった後のひざＩＫ位置を再計算
					kneeIkMat := mmath.NewMMat4()
					kneeIkMat.Translate(kneeDelta.Position)
					kneeIkMat.Translate(model.Bones.GetItemByName(kneeIkBoneName).ParentRelativePosition)
					kneeIkBf.Position = kneeIkMat.Inverted().MulVec3(ankleDelta.Position)
					legIkMotion.AppendBoneFrame(kneeIkBoneName, kneeIkBf)

					// 足首ＩＫはつま先の位置を基準とする
					ankleIkBf := deform.NewBoneFrame(float32(fno))
					toeDelta := ikOffDeltas.GetItem(toeBoneName, float32(fno))
					// ひざＩＫが定まった後の足首ＩＫ位置を再計算
					ankleIkMat := mmath.NewMMat4()
					ankleIkMat.Translate(ankleDelta.Position)
					ankleIkMat.Translate(model.Bones.GetItemByName(ankleIkBoneName).ParentRelativePosition)
					ankleIkBf.Position = ankleIkMat.Inverted().MulVec3(toeDelta.Position)
					legIkMotion.AppendBoneFrame(ankleIkBoneName, ankleIkBf)

					// ひざをグローバルX軸に対して曲げる
					_, _, _, kneeYZQuat := kneeDelta.FrameRotation.SeparateByAxis(model.Bones.GetItemByName(kneeBoneName).NormalizedLocalAxisX)
					kneeBf := deform.NewBoneFrame(float32(fno))
					kneeBf.Rotation.SetQuaternion(mmath.NewMQuaternionFromAxisAngles(mmath.MVec3UnitX, -kneeYZQuat.ToRadian()))
					legIkMotion.AppendRegisteredBoneFrame(kneeBoneName, kneeBf)

					// IKありの変化量を取得
					ikOnDeltas := legIkMotion.AnimateBone(float32(fno), model,
						[]string{legBoneName, kneeBoneName, ankleBoneName, toeBoneName,
							hipIkBoneName, kneeIkBoneName, ankleIkBoneName}, true)

					// 足は足捩りと合成する
					legBf := deform.NewBoneFrame(float32(fno))
					legBf.Rotation.SetQuaternion(
						ikOnDeltas.GetItem(legBoneName, float32(fno)).FrameRotationWithoutEffect.Mul(
							ikOnDeltas.GetItem(hipTwistBoneName, float32(fno)).FrameRotationWithoutEffect),
					)
					legIkMotion.AppendRegisteredBoneFrame(legBoneName, legBf)

					kneeBf = deform.NewBoneFrame(float32(fno))
					kneeBf.Rotation.SetQuaternion(ikOnDeltas.GetItem(kneeBoneName, float32(fno)).FrameRotationWithoutEffect)
					legIkMotion.AppendRegisteredBoneFrame(kneeBoneName, kneeBf)

					ankleBf := deform.NewBoneFrame(float32(fno))
					ankleOnDelta := ikOnDeltas.GetItem(ankleBoneName, float32(fno))
					ankleBf.Rotation.SetQuaternion(ankleOnDelta.FrameRotationWithoutEffect)
					legIkMotion.AppendRegisteredBoneFrame(ankleBoneName, ankleBf)

					// 足ＩＫの位置はIK OFF時の足首位置
					legIkBf := deform.NewBoneFrame(float32(fno))
					legIkBf.Rotation.SetQuaternion(ankleDelta.LocalMatrix.Quaternion())
					legIkBf.Position = ankleDelta.Position.Subed(model.Bones.GetItemByName(ankleBoneName).Position)
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

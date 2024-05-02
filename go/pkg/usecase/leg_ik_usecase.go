package usecase

import (
	"fmt"
	"math"
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
	totalFrames := len(allRotateMotions)
	for _, rotMotion := range allRotateMotions {
		totalFrames += int(rotMotion.GetMaxFrame())
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

	loopLimit := 100

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
					hipTwistBoneName := fmt.Sprintf("%s足捩", direction)
					ankleTwistBoneName := fmt.Sprintf("%s足首捩", direction)
					ankleVBoneName := fmt.Sprintf("%s足首Z垂線", direction)
					toeBigBoneName := fmt.Sprintf("%sつま先親", direction)
					toeSmallBoneName := fmt.Sprintf("%sつま先子", direction)
					kneeIkBoneName := fmt.Sprintf("%sひざＩＫ", direction)
					ankleIkBoneName := fmt.Sprintf("%s足首ＩＫ", direction)
					ankleTwistIkBoneName := fmt.Sprintf("%s足首捩ＩＫ", direction)

					// IKなしの変化量を取得
					legIkOffDeltas := rotMotion.AnimateBone(float32(fno), legIkModel,
						[]string{legBoneName, kneeBoneName, ankleBoneName, ankleVBoneName, toeBoneName,
							toeBigBoneName, toeSmallBoneName, kneeIkBoneName}, false)

					// 足IK --------------------

					// ひざＩＫは足首Z垂線の位置を基準とする
					kneeIkBf := deform.NewBoneFrame(float32(fno))
					ankleVOffDelta := legIkOffDeltas.GetItem(ankleVBoneName, float32(fno))
					kneeIkDelta := legIkOffDeltas.GetItem(kneeIkBoneName, float32(fno))
					kneeIkBf.Position = kneeIkDelta.GlobalMatrix.Inverted().MulVec3(ankleVOffDelta.Position)
					legIkMotion.AppendBoneFrame(kneeIkBoneName, kneeIkBf)

					// ひざをグローバルX軸に対して曲げる
					kneeOffDelta := legIkOffDeltas.GetItem(kneeBoneName, float32(fno))
					_, _, _, kneeYZQuat := kneeOffDelta.FrameRotation.SeparateByAxis(legIkModel.Bones.GetItemByName(kneeBoneName).NormalizedLocalAxisX)
					kneeBf := deform.NewBoneFrame(float32(fno))
					kneeBf.Rotation.SetQuaternion(mmath.NewMQuaternionFromAxisAngles(mmath.MVec3UnitX, -kneeYZQuat.ToRadian()))
					legIkMotion.AppendRegisteredBoneFrame(kneeBoneName, kneeBf)

					// 足首は元の値
					ankleBf := deform.NewBoneFrame(float32(fno))
					ankleBf.Rotation.SetQuaternion(legIkOffDeltas.GetItem(ankleBoneName, float32(fno)).FrameRotationWithoutEffect)
					legIkMotion.AppendRegisteredBoneFrame(ankleBoneName, ankleBf)

					var ankleOnPos *mmath.MVec3
					var legIkOnDeltas *deform.BoneDeltas
					legQuats := make(map[float64]*mmath.MQuaternion, 0)
					anklePoses := make(map[float64]*mmath.MVec3, 0)
					for j := range loopLimit {
						// IKありの変化量を取得
						legIkOnDeltas = legIkMotion.AnimateBone(float32(fno), legIkModel,
							[]string{legBoneName, kneeBoneName, ankleBoneName, ankleVBoneName, kneeIkBoneName}, true)

						kneeOnDelta := legIkOnDeltas.GetItem(kneeBoneName, float32(fno))
						ankleVOnDelta := legIkOnDeltas.GetItem(ankleVBoneName, float32(fno))
						kneeDistance := kneeOnDelta.Position.Distance(kneeOffDelta.Position)
						ankleDistance := ankleVOnDelta.Position.Distance(ankleVOffDelta.Position)

						// 足は足捩りと合成する
						legBf := deform.NewBoneFrame(float32(fno))
						legBf.Rotation.SetQuaternion(
							legIkOnDeltas.GetItem(legBoneName, float32(fno)).FrameRotationWithoutEffect.Mul(
								legIkOnDeltas.GetItem(hipTwistBoneName, float32(fno)).FrameRotationWithoutEffect),
						)
						legIkMotion.AppendRegisteredBoneFrame(legBoneName, legBf)

						// 足捩りの値はクリア
						hipTwistBf := deform.NewBoneFrame(float32(fno))
						legIkMotion.AppendBoneFrame(hipTwistBoneName, hipTwistBf)

						// 足首の位置を保持
						ankleOnPos = legIkOnDeltas.GetItem(ankleBoneName, float32(fno)).Position

						if kneeDistance < 0.1 && ankleDistance < 0.1 {
							mlog.D("[Leg] Converged at [%d][%s][%d] knee: %f ankle: %f", int(fno), direction, j, kneeDistance, ankleDistance)
							break
						}

						legQuats[(kneeDistance+ankleDistance)/2] = legBf.Rotation.GetQuaternion()
						anklePoses[(kneeDistance+ankleDistance)/2] = legIkOnDeltas.GetItem(ankleBoneName, float32(fno)).Position
					}

					if len(legQuats) == loopLimit {
						// 最後まで来まらなかった場合、最も近いものを選択
						minDistance := math.MaxFloat64
						for distance := range legQuats {
							if distance < minDistance {
								minDistance = distance
							}
						}
						mlog.D("*** [Leg] Over Converged at [%d][%s] distance: %f", int(fno), direction, minDistance)

						legBf := deform.NewBoneFrame(float32(fno))
						legBf.Rotation.SetQuaternion(legQuats[minDistance])
						legIkMotion.AppendRegisteredBoneFrame(legBoneName, legBf)

						ankleOnPos = anklePoses[minDistance]
					}

					// IKなしの変化量を取得
					toeIkOffDeltas := rotMotion.AnimateBone(float32(fno), toeIkModel,
						[]string{ankleTwistBoneName, ankleBoneName, toeBoneName, toeBigBoneName, toeSmallBoneName,
							ankleIkBoneName, ankleTwistIkBoneName}, false)

					// 足首の差分（IKありなしで足首の位置が若干ズレるので補正）
					ankleOffDelta := toeIkOffDeltas.GetItem(ankleBoneName, float32(fno))
					ankleDiffPos := ankleOnPos.Subed(ankleOffDelta.Position)

					// 足首ＩＫはつま先親の位置を基準とする
					ankleIkBf := deform.NewBoneFrame(float32(fno))
					toeBigOffDelta := toeIkOffDeltas.GetItem(toeBigBoneName, float32(fno))
					ankleIkBf.Position = toeBigOffDelta.Position.Added(ankleDiffPos).Subed(toeIkModel.Bones.GetItemByName(ankleIkBoneName).Position)
					legIkMotion.AppendBoneFrame(ankleIkBoneName, ankleIkBf)

					// 足首捩ＩＫはつま先子の位置を基準とする
					ankleTwistIkBf := deform.NewBoneFrame(float32(fno))
					toeSmallOffDelta := toeIkOffDeltas.GetItem(toeSmallBoneName, float32(fno))
					// 足首ＩＫが定まった後の足首捩ＩＫ位置を再計算
					ankleTwistIkMat := mmath.NewMMat4()
					ankleTwistIkMat.Translate(ankleDiffPos)
					ankleTwistIkMat.Translate(toeBigOffDelta.Position)
					ankleTwistIkMat.Translate(toeIkModel.Bones.GetItemByName(ankleTwistIkBoneName).ParentRelativePosition)
					ankleTwistIkBf.Position = ankleTwistIkMat.Inverted().MulVec3(toeSmallOffDelta.Position.Added(ankleDiffPos))
					legIkMotion.AppendBoneFrame(ankleTwistIkBoneName, ankleTwistIkBf)

					legIkBf := deform.NewBoneFrame(float32(fno))
					// 足ＩＫの位置はIK OFF時の足首位置
					legIkBf.Position = ankleOffDelta.Position.Subed(toeIkModel.Bones.GetItemByName(ankleBoneName).Position)

					ankleQuats := make(map[float64]*mmath.MQuaternion, 0)
					ankleIkQuats := make(map[float64]*mmath.MQuaternion, 0)
					for j := range loopLimit {
						// IKありの変化量を取得
						ikOnDeltas := legIkMotion.AnimateBone(float32(fno), toeIkModel,
							[]string{ankleBoneName, toeBoneName, toeBigBoneName, toeSmallBoneName, ankleIkBoneName, ankleTwistIkBoneName}, true)

						toeBigOnDelta := ikOnDeltas.GetItem(toeBigBoneName, float32(fno))
						toeSmallOnDelta := ikOnDeltas.GetItem(toeSmallBoneName, float32(fno))
						toeBigDistance := toeBigOnDelta.Position.Distance(toeBigOffDelta.Position.Added(ankleDiffPos))
						toeSmallDistance := toeSmallOnDelta.Position.Distance(toeSmallOffDelta.Position.Added(ankleDiffPos))

						// 足首は足首捩りと合成する
						ankleBf := deform.NewBoneFrame(float32(fno))
						ankleBf.Rotation.SetQuaternion(
							ikOnDeltas.GetItem(ankleBoneName, float32(fno)).FrameRotationWithoutEffect.Mul(
								ikOnDeltas.GetItem(ankleTwistBoneName, float32(fno)).FrameRotationWithoutEffect),
						)
						legIkMotion.AppendRegisteredBoneFrame(ankleBoneName, ankleBf)

						// 足IKの回転は足首までの回転
						legIkBf.Rotation.SetQuaternion(ikOnDeltas.GetItem(ankleBoneName, float32(fno)).LocalMatrix.Quaternion())
						legIkMotion.AppendRegisteredBoneFrame(legIkBoneName, legIkBf)

						// 足首捩りの値はクリア
						ankleTwistBf := deform.NewBoneFrame(float32(fno))
						legIkMotion.AppendBoneFrame(ankleTwistBoneName, ankleTwistBf)

						if toeBigDistance < 0.1 && toeSmallDistance < 0.1 {
							mlog.D("[Toe] Converged at [%d][%s][%d] toeBig: %f toeSmall: %f", int(fno), direction, j, toeBigDistance, toeSmallDistance)
							break
						}

						ankleQuats[(toeBigDistance+toeSmallDistance)/2] = ankleBf.Rotation.GetQuaternion()
						ankleIkQuats[(toeBigDistance+toeSmallDistance)/2] = ikOnDeltas.GetItem(ankleBoneName, float32(fno)).LocalMatrix.Quaternion()
					}

					if len(ankleQuats) == loopLimit {
						// 最後まで来まらなかった場合、最も近いものを選択
						minDistance := math.MaxFloat64
						for distance := range ankleQuats {
							if distance < minDistance {
								minDistance = distance
							}
						}
						mlog.D("*** [Toe] Over Converged at [%d][%s] distance: %f", int(fno), direction, minDistance)

						ankleBf := deform.NewBoneFrame(float32(fno))
						ankleBf.Rotation.SetQuaternion(ankleQuats[minDistance])
						legIkMotion.AppendRegisteredBoneFrame(ankleBoneName, ankleBf)

						legIkBf.Rotation.SetQuaternion(ankleIkQuats[minDistance])
						legIkMotion.AppendRegisteredBoneFrame(legIkBoneName, legIkBf)
					}
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

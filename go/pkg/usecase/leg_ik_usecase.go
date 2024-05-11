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

func ConvertLegIk(allPrevMotions []*vmd.VmdMotion, modelPath string) []*vmd.VmdMotion {
	mlog.I("Start: Leg Ik =============================")

	allLegIkMotions := make([]*vmd.VmdMotion, len(allPrevMotions))

	// mlog.SetLevel(mlog.IK_VERBOSE)

	// 全体のタスク数をカウント
	totalFrames := len(allPrevMotions)
	for _, prevMotion := range allPrevMotions {
		totalFrames += int(prevMotion.BoneFrames.GetItem(pmx.CENTER.String()).GetMaxFrame() - prevMotion.BoneFrames.GetItem(pmx.CENTER.String()).GetMinFrame() + 1.0)
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
			defer mlog.I("[%d/%d] Convert Leg Ik ...", i, len(allPrevMotions))

			legIkMotion := prevMotion.Copy().(*vmd.VmdMotion)

			for fno := prevMotion.BoneFrames.GetItem(pmx.CENTER.String()).GetMinFrame(); fno <= prevMotion.GetMaxFrame(); fno += 1.0 {
				bar.Increment()

				var wg sync.WaitGroup
				errChan := make(chan error, 2) // エラーを受け取るためのチャネル

				calcIk := func(prevMotion *vmd.VmdMotion, legIkMotion *vmd.VmdMotion, direction string) {
					defer wg.Done()

					convertLegIkMotion(prevMotion, legIkMotion, direction, fno, legIkModel, toeIkModel, loopLimit)
				}

				wg.Add(2) // 2つのゴルーチンを待つ

				go calcIk(prevMotion, legIkMotion, "右")
				go calcIk(prevMotion, legIkMotion, "左")

				wg.Wait()      // すべてのゴルーチンが完了するのを待つ
				close(errChan) // チャネルを閉じる

				// エラーがあれば出力
				for err := range errChan {
					mlog.E(err.Error())
				}
			}

			legIkMotion.BoneFrames.Delete("左ももＩＫ")
			legIkMotion.BoneFrames.Delete("左ひざＩＫ")
			legIkMotion.BoneFrames.Delete("左足首ＩＫ")
			legIkMotion.BoneFrames.Delete("左足首捩ＩＫ")
			legIkMotion.BoneFrames.Delete("右ももＩＫ")
			legIkMotion.BoneFrames.Delete("右ひざＩＫ")
			legIkMotion.BoneFrames.Delete("右足首ＩＫ")
			legIkMotion.BoneFrames.Delete("右足首捩ＩＫ")

			legIkMotion.Path = strings.Replace(prevMotion.Path, "_rotate.vmd", "_leg_ik.vmd", -1)
			legIkMotion.SetName(fmt.Sprintf("MAT4 LegIk %02d", i+1))

			err := vmd.Write(legIkMotion)
			if err != nil {
				mlog.E("Failed to write rotate vmd: %v", err)
			}

			allLegIkMotions[i] = legIkMotion
		}(i, prevMotion)
	}

	wg.Wait()
	bar.Finish()

	mlog.I("End: Leg Ik =============================")

	return allLegIkMotions
}

func convertLegIkMotion(
	prevMotion *vmd.VmdMotion, legIkMotion *vmd.VmdMotion, direction string, fno float32,
	legIkModel *pmx.PmxModel, toeIkModel *pmx.PmxModel, loopLimit int,
) {
	legBoneName := pmx.LEG.StringFromDirection(direction)
	kneeBoneName := pmx.KNEE.StringFromDirection(direction)
	ankleBoneName := pmx.ANKLE.StringFromDirection(direction)
	toeBoneName := pmx.TOE.StringFromDirection(direction)
	legIkBoneName := pmx.LEG_IK.StringFromDirection(direction)
	hipTwistBoneName := fmt.Sprintf("%s足捩", direction)
	ankleTwistBoneName := fmt.Sprintf("%s足首捩", direction)
	heelBoneName := fmt.Sprintf("%sかかと", direction)
	toeBigBoneName := fmt.Sprintf("%sつま先親", direction)
	toeSmallBoneName := fmt.Sprintf("%sつま先子", direction)
	hipIkBoneName := fmt.Sprintf("%sももＩＫ", direction)
	kneeIkBoneName := fmt.Sprintf("%sひざＩＫ", direction)
	ankleIkBoneName := fmt.Sprintf("%s足首ＩＫ", direction)
	ankleTwistIkBoneName := fmt.Sprintf("%s足首捩ＩＫ", direction)

	// IKなしの変化量を取得
	legIkOffDeltas := prevMotion.AnimateBone(fno, legIkModel,
		[]string{legBoneName, kneeBoneName, ankleBoneName, toeBoneName, toeSmallBoneName,
			heelBoneName, toeBigBoneName, toeBigBoneName, kneeIkBoneName}, false)

	// 足IK --------------------

	// ももＩＫはひざの位置を基準とする
	hipIkBf := deform.NewBoneFrame(fno)
	kneeOffDelta := legIkOffDeltas.GetItem(kneeBoneName, fno)
	hipIkBf.Position = kneeOffDelta.Position.Subed(legIkModel.Bones.GetItemByName(hipIkBoneName).Position)
	legIkMotion.AppendBoneFrame(hipIkBoneName, hipIkBf)

	// ひざＩＫは足首の位置を基準とする
	kneeIkBf := deform.NewBoneFrame(fno)
	ankleOffDelta := legIkOffDeltas.GetItem(ankleBoneName, fno)
	kneeIkBf.Position = ankleOffDelta.Position.Subed(hipIkBf.Position).Subed(legIkModel.Bones.GetItemByName(kneeIkBoneName).Position)
	legIkMotion.AppendBoneFrame(kneeIkBoneName, kneeIkBf)

	// ひざをグローバルX軸に対して曲げる
	_, _, _, kneeYZQuat := kneeOffDelta.FrameRotation.SeparateByAxis(legIkModel.Bones.GetItemByName(kneeBoneName).NormalizedLocalAxisX)
	kneeBf := deform.NewBoneFrame(fno)
	kneeBf.Rotation.SetQuaternion(mmath.NewMQuaternionFromAxisAngles(mmath.MVec3UnitX, -kneeYZQuat.ToRadian()))
	legIkMotion.AppendRegisteredBoneFrame(kneeBoneName, kneeBf)

	// 初期時点の足首の位置
	ankleByLegPos := legIkOffDeltas.GetItem(ankleBoneName, fno).Position

	if mlog.IsVerbose() {
		legIkMotion.Path = strings.Replace(prevMotion.Path, "wrist.vmd", direction+"_leg_ik_0.vmd", -1)
		err := vmd.Write(legIkMotion)
		if err != nil {
			mlog.E("Failed to write leg ik vmd: %v", err)
		}
	}

	var legIkOnDeltas *deform.BoneDeltas
	var legQuat *mmath.MQuaternion
	legKey := math.MaxFloat64
	for j := range loopLimit {
		// IKありの変化量を取得
		legIkOnDeltas = legIkMotion.AnimateBone(fno, legIkModel,
			[]string{legBoneName, kneeBoneName, ankleBoneName, kneeIkBoneName}, true)

		kneeOnDelta := legIkOnDeltas.GetItem(kneeBoneName, fno)
		ankleOnDelta := legIkOnDeltas.GetItem(ankleBoneName, fno)
		kneeDistance := kneeOnDelta.Position.Distance(kneeOffDelta.Position)
		ankleDistance := ankleOnDelta.Position.Distance(ankleOffDelta.Position)

		// 足は足捩りと合成する
		legBf := deform.NewBoneFrame(fno)
		legBf.Rotation.SetQuaternion(
			legIkOnDeltas.GetItem(legBoneName, fno).FrameRotationWithoutEffect.Mul(
				legIkOnDeltas.GetItem(hipTwistBoneName, fno).FrameRotationWithoutEffect),
		)
		legIkMotion.AppendRegisteredBoneFrame(legBoneName, legBf)

		// 足捩りの値はクリア
		hipTwistBf := deform.NewBoneFrame(fno)
		legIkMotion.AppendBoneFrame(hipTwistBoneName, hipTwistBf)

		keySum := kneeDistance + ankleDistance

		mlog.V("[Leg] Distance [%d][%s][%d] knee: %f, ankle: %f, keySum: %f, legKey: %f",
			int(fno), direction, j, kneeDistance, ankleDistance, keySum, legKey)

		if keySum < legKey {
			legKey = keySum
			legQuat = legBf.Rotation.GetQuaternion()
		}

		if kneeDistance < 1e-3 && ankleDistance < 0.1 {
			mlog.V("*** [Leg] Converged at [%d][%s][%d] knee: %f, ankle: %f, keySum: %f, legKey: %f",
				int(fno), direction, j, kneeDistance, ankleDistance, keySum, legKey)
			break
		}
	}

	// 最も近いものを採用
	mlog.V("[Leg] FIX Converged at [%d][%s] distance: %f(%s)", int(fno), direction, legKey, legQuat.ToDegrees().String())

	// 足は足捩りと合成した値を設定
	legBf := deform.NewBoneFrame(fno)
	legBf.Rotation.SetQuaternion(legQuat)
	legIkMotion.AppendRegisteredBoneFrame(legBoneName, legBf)

	if mlog.IsVerbose() {
		legIkMotion.Path = strings.Replace(prevMotion.Path, "wrist.vmd", direction+"_leg_ik_1.vmd", -1)
		err := vmd.Write(legIkMotion)
		if err != nil {
			mlog.E("Failed to write leg ik vmd: %v", err)
		}
	}

	// 足系解決後の足首位置を取得
	toeIkOffDeltas := legIkMotion.AnimateBone(fno, toeIkModel, []string{ankleBoneName}, false)

	// 足首位置の差分を取る
	ankleByToePos := toeIkOffDeltas.GetItem(ankleBoneName, fno).Position
	ankleDiffVec := ankleByToePos.Subed(ankleByLegPos)

	// 足首ＩＫはつま先の位置を基準とする
	ankleIkBf := deform.NewBoneFrame(fno)
	toeOffDelta := legIkOffDeltas.GetItem(toeBoneName, fno)
	ankleIkBf.Position = toeOffDelta.Position.Added(ankleDiffVec).Subed(toeIkModel.Bones.GetItemByName(ankleIkBoneName).Position)
	legIkMotion.AppendBoneFrame(ankleIkBoneName, ankleIkBf)

	// 足首捩ＩＫはつま先親の位置を基準とする
	ankleTwistIkBf := deform.NewBoneFrame(fno)
	toeBigOffDelta := legIkOffDeltas.GetItem(toeBigBoneName, fno)
	ankleTwistIkBf.Position = toeBigOffDelta.Position.Added(ankleDiffVec).
		Subed(ankleIkBf.Position).Subed(toeIkModel.Bones.GetItemByName(ankleTwistIkBoneName).Position)
	legIkMotion.AppendBoneFrame(ankleTwistIkBoneName, ankleTwistIkBf)

	toeOffPos := legIkOffDeltas.GetItem(toeBoneName, fno).Position.Added(ankleDiffVec)
	toeSmallOffPos := legIkOffDeltas.GetItem(toeSmallBoneName, fno).Position.Added(ankleDiffVec)
	heelOffPos := legIkOffDeltas.GetItem(heelBoneName, fno).Position.Added(ankleDiffVec)

	// 足ＩＫの位置はIK OFF時の足首位置
	legIkBf := deform.NewBoneFrame(fno)
	legIkBf.Position = ankleOffDelta.Position.Added(ankleDiffVec).Subed(toeIkModel.Bones.GetItemByName(ankleBoneName).Position)

	if mlog.IsVerbose() {
		legIkMotion.Path = strings.Replace(prevMotion.Path, "wrist.vmd", direction+"_leg_ik_2.vmd", -1)
		err := vmd.Write(legIkMotion)
		if err != nil {
			mlog.E("Failed to write leg ik vmd: %v", err)
		}
	}

	ankleKey := math.MaxFloat64
	var ankleIkQuat *mmath.MQuaternion
	for k := range loopLimit {
		// IKありの変化量を取得
		ikOnDeltas := legIkMotion.AnimateBone(fno, toeIkModel,
			[]string{ankleBoneName, toeBoneName, toeSmallBoneName, heelBoneName, ankleIkBoneName, ankleTwistBoneName}, true)

		toeOnPos := ikOnDeltas.GetItem(toeBoneName, fno).Position
		toeDistance := toeOnPos.Distance(toeOffPos)
		toeOnSmallPos := ikOnDeltas.GetItem(toeSmallBoneName, fno).Position
		toeSmallDistance := toeOnSmallPos.Distance(toeSmallOffPos)
		heelOnPos := ikOnDeltas.GetItem(heelBoneName, fno).Position
		heelDistance := heelOnPos.Distance(heelOffPos)

		// 足首は足首捩りと合成する
		ankleBf := deform.NewBoneFrame(fno)
		ankleBf.Rotation.SetQuaternion(
			ikOnDeltas.GetItem(ankleBoneName, fno).FrameRotationWithoutEffect.Mul(
				ikOnDeltas.GetItem(ankleTwistBoneName, fno).FrameRotationWithoutEffect),
		)
		legIkMotion.AppendRegisteredBoneFrame(ankleBoneName, ankleBf)

		// 足首捩りの値はクリア
		ankleTwistBf := deform.NewBoneFrame(fno)
		legIkMotion.AppendBoneFrame(ankleTwistBoneName, ankleTwistBf)

		keySum := toeDistance + toeSmallDistance + heelDistance

		mlog.V("[Toe] Distance [%d][%s][%d] toe: %f toeSmall: %f heel: %f, keySum: %f, ankleKey: %f",
			int(fno), direction, k, toeDistance, toeSmallDistance, heelDistance, keySum, ankleKey)

		if keySum < ankleKey {
			ankleKey = keySum
			ankleIkQuat = ikOnDeltas.GetItem(ankleBoneName, fno).LocalMatrix.Quaternion()
		}

		if toeDistance < 1e-3 && toeSmallDistance < 0.1 && heelDistance < 0.1 {
			mlog.V("*** [Toe] Converged at [%d][%s][%d] toe: %f toeSmall: %f heel: %f", int(fno), direction, k,
				toeDistance, toeSmallDistance, heelDistance)
			break
		}
	}

	// 最も近いものを採用
	mlog.V("[Toe] FIX Converged at [%d][%s] distance: %f(%s)", int(fno), direction, ankleKey, ankleIkQuat.ToDegrees().String())

	// 足IKの回転は足首までの回転
	legIkBf.Rotation.SetQuaternion(ankleIkQuat)
	legIkMotion.AppendRegisteredBoneFrame(legIkBoneName, legIkBf)
}

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

func ConvertLegIk(prevMotion *vmd.VmdMotion, modelPath string, motionNum, allNum int) *vmd.VmdMotion {
	mlog.I("[%d/%d] Convert Leg Ik ...", motionNum, allNum)

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

	minFrame := prevMotion.BoneFrames.Get(pmx.CENTER.String()).GetMinFrame()
	maxFrame := prevMotion.BoneFrames.Get(pmx.CENTER.String()).GetMaxFrame()

	bar := utils.NewProgressBar(maxFrame - minFrame)

	loopLimit := 100

	legIkMotion := prevMotion.Copy().(*vmd.VmdMotion)

	for fno := minFrame; fno <= maxFrame; fno++ {
		bar.Increment()

		convertLegIkMotion(prevMotion, legIkMotion, "右", fno, legIkModel, toeIkModel, loopLimit)
		convertLegIkMotion(prevMotion, legIkMotion, "左", fno, legIkModel, toeIkModel, loopLimit)
	}

	legIkMotion.BoneFrames.Delete("左ももＩＫ")
	legIkMotion.BoneFrames.Delete("左ひざＩＫ")
	legIkMotion.BoneFrames.Delete("左足首ＩＫ")
	legIkMotion.BoneFrames.Delete("左足首捩ＩＫ")
	legIkMotion.BoneFrames.Delete("右ももＩＫ")
	legIkMotion.BoneFrames.Delete("右ひざＩＫ")
	legIkMotion.BoneFrames.Delete("右足首ＩＫ")
	legIkMotion.BoneFrames.Delete("右足首捩ＩＫ")

	bar.Finish()

	return legIkMotion
}

func convertLegIkMotion(
	prevMotion, legIkMotion *vmd.VmdMotion, direction string, fno int, legIkModel *pmx.PmxModel, toeIkModel *pmx.PmxModel, loopLimit int,
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
	hipIkBf := vmd.NewBoneFrame(fno)
	kneeOffDelta := legIkOffDeltas.Get(kneeBoneName)
	hipIkBf.Position = kneeOffDelta.Position.Subed(legIkModel.Bones.GetByName(hipIkBoneName).Position)
	legIkMotion.AppendBoneFrame(hipIkBoneName, hipIkBf)

	// ひざＩＫは足首の位置を基準とする
	kneeIkBf := vmd.NewBoneFrame(fno)
	ankleOffDelta := legIkOffDeltas.Get(ankleBoneName)
	kneeIkBf.Position = ankleOffDelta.Position.Subed(hipIkBf.Position).Subed(legIkModel.Bones.GetByName(kneeIkBoneName).Position)
	legIkMotion.AppendBoneFrame(kneeIkBoneName, kneeIkBf)

	// ひざをグローバルX軸に対して曲げる
	_, _, _, kneeYZQuat := kneeOffDelta.FrameRotation.SeparateByAxis(legIkModel.Bones.GetByName(kneeBoneName).NormalizedLocalAxisX)
	kneeBf := vmd.NewBoneFrame(fno)
	kneeQuat := mmath.NewMQuaternionFromAxisAngles(mmath.MVec3UnitX, -kneeYZQuat.ToRadian())
	kneeBf.Rotation = mmath.NewRotationByQuaternion(kneeQuat)
	legIkMotion.AppendRegisteredBoneFrame(kneeBoneName, kneeBf)

	// 初期時点の足首の位置
	ankleByLegPos := legIkOffDeltas.Get(ankleBoneName).Position

	// if mlog.IsVerbose() {
	// 	legIkMotion.Path = strings.Replace(prevMotion.Path, "wrist.vmd", direction+"_leg_ik_0.vmd", -1)
	// 	err := vmd.Write(legIkMotion)
	// 	if err != nil {
	// 		mlog.E("Failed to write leg ik vmd: %v", err)
	// 	}
	// }

	var legIkOnDeltas *vmd.BoneDeltas
	var legQuat *mmath.MQuaternion
	legKey := math.MaxFloat64
	for j := range loopLimit {
		// IKありの変化量を取得
		legIkOnDeltas = legIkMotion.AnimateBone(fno, legIkModel,
			[]string{legBoneName, kneeBoneName, ankleBoneName, kneeIkBoneName}, true)

		kneeOnDelta := legIkOnDeltas.Get(kneeBoneName)
		ankleOnDelta := legIkOnDeltas.Get(ankleBoneName)
		kneeDistance := kneeOnDelta.Position.Distance(kneeOffDelta.Position)
		ankleDistance := ankleOnDelta.Position.Distance(ankleOffDelta.Position)

		// 足は足捩りと合成する
		legBf := vmd.NewBoneFrame(fno)
		legBf.Rotation.SetQuaternion(
			legIkOnDeltas.Get(legBoneName).FrameRotationWithoutEffect.Mul(
				legIkOnDeltas.Get(hipTwistBoneName).FrameRotationWithoutEffect),
		)
		legIkMotion.AppendRegisteredBoneFrame(legBoneName, legBf)

		// 足捩りの値はクリア
		hipTwistBf := vmd.NewBoneFrame(fno)
		legIkMotion.AppendBoneFrame(hipTwistBoneName, hipTwistBf)

		keySum := kneeDistance + ankleDistance

		mlog.V("[Leg] Distance [%d][%s][%d] knee: %f, ankle: %f, keySum: %f, legKey: %f",
			fno, direction, j, kneeDistance, ankleDistance, keySum, legKey)

		if keySum < legKey {
			legKey = keySum
			legQuat = legBf.Rotation.GetQuaternion()
		}

		if kneeDistance < 1e-3 && ankleDistance < 0.1 {
			mlog.V("*** [Leg] Converged at [%d][%s][%d] knee: %f, ankle: %f, keySum: %f, legKey: %f",
				fno, direction, j, kneeDistance, ankleDistance, keySum, legKey)
			break
		}
	}

	// 最も近いものを採用
	mlog.V("[Leg] FIX Converged at [%d][%s] distance: %f(%s)", fno, direction, legKey, legQuat.ToDegrees().String())

	// 足は足捩りと合成した値を設定
	legBf := vmd.NewBoneFrame(fno)
	legBf.Rotation.SetQuaternion(legQuat)
	legIkMotion.AppendRegisteredBoneFrame(legBoneName, legBf)

	// if mlog.IsVerbose() {
	// 	legIkMotion.Path = strings.Replace(prevMotion.Path, "wrist.vmd", direction+"_leg_ik_1.vmd", -1)
	// 	err := vmd.Write(legIkMotion)
	// 	if err != nil {
	// 		mlog.E("Failed to write leg ik vmd: %v", err)
	// 	}
	// }

	// 足系解決後の足首位置を取得
	toeIkOffDeltas := legIkMotion.AnimateBone(fno, toeIkModel, []string{ankleBoneName}, false)

	// 足首位置の差分を取る
	ankleByToePos := toeIkOffDeltas.Get(ankleBoneName).Position
	ankleDiffVec := ankleByToePos.Subed(ankleByLegPos)

	// 足首ＩＫはつま先の位置を基準とする
	ankleIkBf := vmd.NewBoneFrame(fno)
	toeOffDelta := legIkOffDeltas.Get(toeBoneName)
	ankleIkBf.Position = toeOffDelta.Position.Added(ankleDiffVec).Subed(toeIkModel.Bones.GetByName(ankleIkBoneName).Position)
	legIkMotion.AppendBoneFrame(ankleIkBoneName, ankleIkBf)

	// 足首捩ＩＫはつま先親の位置を基準とする
	ankleTwistIkBf := vmd.NewBoneFrame(fno)
	toeBigOffDelta := legIkOffDeltas.Get(toeBigBoneName)
	ankleTwistIkBf.Position = toeBigOffDelta.Position.Added(ankleDiffVec).
		Subed(ankleIkBf.Position).Subed(toeIkModel.Bones.GetByName(ankleTwistIkBoneName).Position)
	legIkMotion.AppendBoneFrame(ankleTwistIkBoneName, ankleTwistIkBf)

	toeOffPos := legIkOffDeltas.Get(toeBoneName).Position.Added(ankleDiffVec)
	toeSmallOffPos := legIkOffDeltas.Get(toeSmallBoneName).Position.Added(ankleDiffVec)
	heelOffPos := legIkOffDeltas.Get(heelBoneName).Position.Added(ankleDiffVec)

	// 足ＩＫの位置はIK OFF時の足首位置
	legIkBf := vmd.NewBoneFrame(fno)
	legIkBf.Position = ankleOffDelta.Position.Added(ankleDiffVec).Subed(toeIkModel.Bones.GetByName(ankleBoneName).Position)

	// if mlog.IsVerbose() {
	// 	legIkMotion.Path = strings.Replace(prevMotion.Path, "wrist.vmd", direction+"_leg_ik_2.vmd", -1)
	// 	err := vmd.Write(legIkMotion)
	// 	if err != nil {
	// 		mlog.E("Failed to write leg ik vmd: %v", err)
	// 	}
	// }

	ankleKey := math.MaxFloat64
	var ankleIkQuat *mmath.MQuaternion
	for k := range loopLimit {
		// IKありの変化量を取得
		ikOnDeltas := legIkMotion.AnimateBone(fno, toeIkModel,
			[]string{ankleBoneName, toeBoneName, toeSmallBoneName, heelBoneName, ankleIkBoneName, ankleTwistBoneName}, true)

		toeOnPos := ikOnDeltas.Get(toeBoneName).Position
		toeDistance := toeOnPos.Distance(toeOffPos)
		toeOnSmallPos := ikOnDeltas.Get(toeSmallBoneName).Position
		toeSmallDistance := toeOnSmallPos.Distance(toeSmallOffPos)
		heelOnPos := ikOnDeltas.Get(heelBoneName).Position
		heelDistance := heelOnPos.Distance(heelOffPos)

		// 足首は足首捩りと合成する
		ankleBf := vmd.NewBoneFrame(fno)
		ankleBf.Rotation.SetQuaternion(
			ikOnDeltas.Get(ankleBoneName).FrameRotationWithoutEffect.Mul(
				ikOnDeltas.Get(ankleTwistBoneName).FrameRotationWithoutEffect),
		)
		legIkMotion.AppendRegisteredBoneFrame(ankleBoneName, ankleBf)

		// 足首捩りの値はクリア
		ankleTwistBf := vmd.NewBoneFrame(fno)
		legIkMotion.AppendBoneFrame(ankleTwistBoneName, ankleTwistBf)

		keySum := toeDistance + toeSmallDistance + heelDistance

		mlog.V("[Toe] Distance [%d][%s][%d] toe: %f toeSmall: %f heel: %f, keySum: %f, ankleKey: %f",
			fno, direction, k, toeDistance, toeSmallDistance, heelDistance, keySum, ankleKey)

		if keySum < ankleKey {
			ankleKey = keySum
			ankleIkQuat = ikOnDeltas.Get(ankleBoneName).LocalMatrix.Quaternion()
		}

		if toeDistance < 1e-3 && toeSmallDistance < 0.1 && heelDistance < 0.1 {
			mlog.V("*** [Toe] Converged at [%d][%s][%d] toe: %f toeSmall: %f heel: %f", fno, direction, k,
				toeDistance, toeSmallDistance, heelDistance)
			break
		}
	}

	// 最も近いものを採用
	mlog.V("[Toe] FIX Converged at [%d][%s] distance: %f(%s)", fno, direction, ankleKey, ankleIkQuat.ToDegrees().String())

	// 足IKの回転は足首までの回転
	legIkBf.Rotation.SetQuaternion(ankleIkQuat)
	legIkMotion.AppendRegisteredBoneFrame(legIkBoneName, legIkBf)
}

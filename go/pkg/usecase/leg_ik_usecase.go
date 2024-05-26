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

	// 足首IK用モデル読み込み
	toeIkData, err := pr.ReadByFilepath(strings.Replace(modelPath, ".pmx", "_toe_ik.pmx", -1))
	if err != nil {
		mlog.E("Failed to read pmx: %v", err)
	}
	toeIkModel := toeIkData.(*pmx.PmxModel)

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
	prevMotion, legIkMotion *vmd.VmdMotion, direction string, fno int, legIkModel, toeIkModel *pmx.PmxModel, loopLimit int,
) {

	mlog.SetLevel(mlog.DEBUG)

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
	// toeIkBoneName := fmt.Sprintf("%sつま先ＩＫ", direction)

	// IKなしの変化量を取得
	legIkOffDeltas := prevMotion.BoneFrames.Deform(fno, legIkModel,
		[]string{legBoneName, kneeBoneName, ankleBoneName, toeBoneName, heelBoneName, toeBigBoneName, toeSmallBoneName,
			hipIkBoneName, kneeIkBoneName}, false, nil)

	// 足IK --------------------

	// ももＩＫはひざの位置を基準とする
	hipIkBf := vmd.NewBoneFrame(fno)
	kneeOffDelta := legIkOffDeltas.GetByName(kneeBoneName)
	hipIkBf.Position = kneeOffDelta.GlobalPosition().Subed(legIkModel.Bones.GetByName(hipIkBoneName).Position)
	legIkMotion.AppendBoneFrame(hipIkBoneName, hipIkBf)

	// ひざＩＫは足首の位置を基準とする
	kneeIkBf := vmd.NewBoneFrame(fno)
	ankleOffDelta := legIkOffDeltas.GetByName(ankleBoneName)
	kneeIkBf.Position = ankleOffDelta.GlobalPosition().Subed(hipIkBf.Position).Subed(legIkModel.Bones.GetByName(kneeIkBoneName).Position)
	legIkMotion.AppendBoneFrame(kneeIkBoneName, kneeIkBf)

	// ひざをグローバルX軸に対して曲げる
	_, kneeYZQuat := kneeOffDelta.GlobalRotation().SeparateTwistByAxis(legIkModel.Bones.GetByName(kneeBoneName).NormalizedLocalAxisX)
	kneeBf := vmd.NewBoneFrame(fno)
	kneeQuat := mmath.NewMQuaternionFromAxisAngles(mmath.MVec3UnitX, -kneeYZQuat.ToRadian())
	kneeBf.Rotation = mmath.NewRotationByQuaternion(kneeQuat)
	legIkMotion.AppendRegisteredBoneFrame(kneeBoneName, kneeBf)

	// if mlog.IsVerbose() {
	// 	legIkMotion.Path = strings.Replace(prevMotion.Path, "wrist.vmd", direction+"_leg_ik_0.vmd", -1)
	// 	err := vmd.Write(legIkMotion)
	// 	if err != nil {
	// 		mlog.E("Failed to write leg ik vmd: %v", err)
	// 	}
	// }

	var legIkOnDeltas *vmd.BoneDeltas
	var legQuat *mmath.MQuaternion
	legKeySum := math.MaxFloat64
	legKeyAvg := math.MaxFloat64
	for j := range loopLimit {
		// IKありの変化量を取得
		legIkOnDeltas = legIkMotion.BoneFrames.Deform(fno, legIkModel,
			[]string{legBoneName, kneeBoneName, ankleBoneName, hipIkBoneName, kneeIkBoneName}, true, nil)

		kneeOnDelta := legIkOnDeltas.GetByName(kneeBoneName)
		ankleOnDelta := legIkOnDeltas.GetByName(ankleBoneName)
		kneeDistance := kneeOnDelta.GlobalPosition().Distance(kneeOffDelta.GlobalPosition())
		ankleDistance := ankleOnDelta.GlobalPosition().Distance(ankleOffDelta.GlobalPosition())

		// 足は足捩りと合成する
		legBf := vmd.NewBoneFrame(fno)
		legBf.Rotation.SetQuaternion(
			legIkOnDeltas.GetByName(hipTwistBoneName).GlobalRotation().Mul(
				legIkOnDeltas.GetByName(legBoneName).GlobalRotation()),
		)
		legIkMotion.AppendRegisteredBoneFrame(legBoneName, legBf)

		// 足捩りの値はクリア
		hipTwistBf := vmd.NewBoneFrame(fno)
		legIkMotion.AppendBoneFrame(hipTwistBoneName, hipTwistBf)

		keySum := kneeDistance + ankleDistance
		keyAvg := keySum / 2

		mlog.V("[Leg] Distance [%d][%s][%d] knee: %f, ankle: %f, keySum: %f, legKeySum: %f, legKeyAvg: %f, legQuat: %v",
			fno, direction, j, kneeDistance, ankleDistance, keySum, keyAvg, legKeySum, legBf.Rotation.GetDegreesMMD())

		if keySum < legKeySum && keyAvg < legKeyAvg {
			legKeySum = keySum
			legQuat = legBf.Rotation.GetQuaternion()
		}

		if kneeDistance < 1e-3 && ankleDistance < 0.1 {
			mlog.V("*** [Leg] Converged at [%d][%s][%d] knee: %f, ankle: %f, keySum: %f, keyAvg: %v legKey: %f",
				fno, direction, j, kneeDistance, ankleDistance, keySum, keyAvg, legKeySum)
			break
		}
	}

	// 最も近いものを採用
	mlog.V("[Leg] FIX Converged at [%d][%s] distance: %f(%s)", fno, direction, legKeySum, legQuat.MMD().ToDegrees().String())

	// 足は足捩りと合成した値を設定
	legBf := vmd.NewBoneFrame(fno)
	legBf.Rotation.SetQuaternion(legQuat)
	legIkMotion.AppendRegisteredBoneFrame(legBoneName, legBf)

	// 足IK結果の変化量を取得
	legOnDeltas := legIkMotion.BoneFrames.Deform(fno, legIkModel, []string{ankleBoneName, toeBoneName}, true, nil)

	// 足首の位置の差分を取得
	ankleDiffPos := legOnDeltas.GetByName(ankleBoneName).GlobalPosition().Subed(legIkOffDeltas.GetByName(ankleBoneName).GlobalPosition())

	// // つま先ＩＫはつま先の位置を基準とする
	// toeIkBf := vmd.NewBoneFrame(fno)
	// toeOffPos := legIkOffDeltas.GetByName(toeBoneName).GlobalPosition()
	// toeIkBf.Position = toeOffPos.Sub(toeIkModel.Bones.GetByName(toeIkBoneName).Position).Add(ankleDiffPos)
	// legIkMotion.AppendBoneFrame(toeIkBoneName, toeIkBf)

	// // IKありの変化量を取得
	// toeIkOnDeltas := legIkMotion.BoneFrames.Deform(fno, toeIkModel,
	// 	[]string{ankleBoneName, toeBoneName, toeIkBoneName}, true, true, false, nil)

	// if mlog.IsVerbose() {
	// 	legIkMotion.Path = strings.Replace(prevMotion.Path, "wrist.vmd", direction+"_leg_ik_1.vmd", -1)
	// 	err := vmd.Write(legIkMotion)
	// 	if err != nil {
	// 		mlog.E("Failed to write leg ik vmd: %v", err)
	// 	}
	// }

	// mlog.SetLevel(mlog.IK_VERBOSE)

	// if mlog.IsIkVerbose() {
	// 	legIkMotion.Path = strings.Replace(prevMotion.Path, "2_rotate.vmd", direction+"_leg_ik_2.vmd", -1)
	// 	err := vmd.Write(legIkMotion)
	// 	if err != nil {
	// 		mlog.E("Failed to write leg ik vmd: %v", err)
	// 	}
	// }

	toeOffPos := legIkOffDeltas.GetByName(toeBoneName).GlobalPosition().Added(ankleDiffPos)
	toeSmallOffPos := legIkOffDeltas.GetByName(toeSmallBoneName).GlobalPosition().Added(ankleDiffPos)
	heelOffPos := legIkOffDeltas.GetByName(heelBoneName).GlobalPosition().Added(ankleDiffPos)

	// 足首ＩＫはつま先の位置を基準とする
	toeIkBf := vmd.NewBoneFrame(fno)
	toeOffDelta := legIkOffDeltas.GetByName(toeBoneName)
	toeIkBf.Position = toeOffDelta.GlobalPosition().Subed(toeIkModel.Bones.GetByName(ankleIkBoneName).Position).Add(ankleDiffPos)
	legIkMotion.AppendBoneFrame(ankleIkBoneName, toeIkBf)

	// 足首捩ＩＫはつま先親の位置を基準とする
	ankleTwistIkBf := vmd.NewBoneFrame(fno)
	toeBigOffDelta := legIkOffDeltas.GetByName(toeBigBoneName)
	ankleTwistIkBf.Position = toeBigOffDelta.GlobalPosition().
		Subed(toeIkBf.Position).Subed(toeIkModel.Bones.GetByName(ankleTwistIkBoneName).Position).Add(ankleDiffPos)
	legIkMotion.AppendBoneFrame(ankleTwistIkBoneName, ankleTwistIkBf)

	ankleKeySum := math.MaxFloat64
	ankleKeyAvg := math.MaxFloat64
	var ankleQuat, ankleIkQuat *mmath.MQuaternion
	for k := range loopLimit {
		// IKありの変化量を取得
		ikOnDeltas := legIkMotion.BoneFrames.Deform(fno, toeIkModel,
			[]string{ankleBoneName, toeBoneName, toeSmallBoneName, heelBoneName, ankleIkBoneName, ankleTwistBoneName}, true, nil)

		toeOnPos := ikOnDeltas.GetByName(toeBoneName).GlobalPosition()
		toeDistance := toeOnPos.Distance(toeOffPos)
		toeOnSmallPos := ikOnDeltas.GetByName(toeSmallBoneName).GlobalPosition()
		toeSmallDistance := toeOnSmallPos.Distance(toeSmallOffPos)
		heelOnPos := ikOnDeltas.GetByName(heelBoneName).GlobalPosition()
		heelDistance := heelOnPos.Distance(heelOffPos)

		// 足首は足首捩りと合成する
		ankleBf := vmd.NewBoneFrame(fno)
		ankleBf.Rotation.SetQuaternion(
			ikOnDeltas.GetByName(ankleTwistBoneName).GlobalRotation().Mul(
				ikOnDeltas.GetByName(ankleBoneName).GlobalRotation()),
		)
		legIkMotion.AppendRegisteredBoneFrame(ankleBoneName, ankleBf)

		// 足首捩りの値はクリア
		ankleTwistBf := vmd.NewBoneFrame(fno)
		legIkMotion.AppendBoneFrame(ankleTwistBoneName, ankleTwistBf)

		keySum := toeDistance + toeSmallDistance + heelDistance
		keyAvg := keySum / 3

		mlog.D("[Toe] Distance [%d][%s][%d] toe: %f toeSmall: %f heel: %f, keySum: %f, keyAvg: %f, ankleKey: %f",
			fno, direction, k, toeDistance, toeSmallDistance, heelDistance, keySum, keyAvg, ankleKeySum)

		if keySum < ankleKeySum && keyAvg < ankleKeyAvg {
			ankleKeySum = keySum
			ankleKeyAvg = keyAvg
			ankleQuat = ankleBf.Rotation.GetQuaternion()
			ankleIkQuat = ikOnDeltas.GetByName(ankleBoneName).LocalMatrix().Quaternion().Inverted()
			mlog.D("** [Toe] Replaced Distance [%d][%s][%d] toe: %f toeSmall: %f heel: %f, keySum: %f, keyAvg: %f, ankleKey: %f",
				fno, direction, k, toeDistance, toeSmallDistance, heelDistance, keySum, keyAvg, ankleKeySum)
		}

		if toeDistance < 1e-3 && toeSmallDistance < 0.1 && heelDistance < 0.1 {
			mlog.D("*** [Toe] Converged at [%d][%s][%d] toe: %f toeSmall: %f heel: %f", fno, direction, k,
				toeDistance, toeSmallDistance, heelDistance)
			break
		}
	}

	// 最も近いものを採用
	mlog.D("[Toe] FIX Converged at [%d][%s] distance: %f(%s)", fno, direction, ankleKeySum, ankleQuat.MMD().ToDegrees().String())

	// 足首
	ankleBf := vmd.NewBoneFrame(fno)
	ankleBf.Rotation.SetQuaternion(ankleQuat)

	// 足ＩＫの位置はIK OFF時の足首位置
	legIkBf := vmd.NewBoneFrame(fno)
	legIkBf.Position = ankleOffDelta.GlobalPosition().Subed(toeIkModel.Bones.GetByName(ankleBoneName).Position)
	legIkBf.Rotation.SetQuaternion(ankleIkQuat)
	legIkMotion.AppendRegisteredBoneFrame(legIkBoneName, legIkBf)
}

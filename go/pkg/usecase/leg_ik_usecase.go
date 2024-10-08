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
	mlog.D("[%d/%d] Convert Leg Ik ...", motionNum, allNum)

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

	legIkMotion := prevMotion.Copy().(*vmd.VmdMotion)

	for fno := minFrame; fno <= maxFrame; fno++ {
		bar.Increment()

		// isPrevCopy := fno > minFrame && legIkMotion.BoneFrames.Get(pmx.CENTER.String()).Contains(fno-1)
		convertLegIkMotion(prevMotion, legIkMotion, "右", fno, legIkModel, toeIkModel)
		convertLegIkMotion(prevMotion, legIkMotion, "左", fno, legIkModel, toeIkModel)
	}

	legIkMotion.BoneFrames.Delete("左ももＩＫ")
	legIkMotion.BoneFrames.Delete("左ひざＩＫ")
	legIkMotion.BoneFrames.Delete("左足首ＩＫ")
	legIkMotion.BoneFrames.Delete("左足首捩ＩＫ")
	legIkMotion.BoneFrames.Delete("左足捩")
	legIkMotion.BoneFrames.Delete("左足首捩")
	legIkMotion.BoneFrames.Delete("右ももＩＫ")
	legIkMotion.BoneFrames.Delete("右ひざＩＫ")
	legIkMotion.BoneFrames.Delete("右足首ＩＫ")
	legIkMotion.BoneFrames.Delete("右足首捩ＩＫ")
	legIkMotion.BoneFrames.Delete("右足捩")
	legIkMotion.BoneFrames.Delete("右足首捩")

	bar.Finish()

	return legIkMotion
}

func convertLegIkMotion(
	prevMotion, legIkMotion *vmd.VmdMotion, direction string, fno int, legIkModel, toeIkModel *pmx.PmxModel,
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
	legTwistIkBoneName := fmt.Sprintf("%s足捩ＩＫ", direction)
	kneeIkBoneName := fmt.Sprintf("%sひざＩＫ", direction)
	ankleIkBoneName := fmt.Sprintf("%s足首ＩＫ", direction)
	ankleTwistIkBoneName := fmt.Sprintf("%s足首捩ＩＫ", direction)
	// toeIkBoneName := fmt.Sprintf("%sつま先ＩＫ", direction)

	// IKなしの変化量を取得
	legIkOffDeltas := prevMotion.BoneFrames.Deform(fno, legIkModel,
		[]string{legBoneName, kneeBoneName, ankleBoneName, toeBoneName, heelBoneName, toeBigBoneName, toeSmallBoneName,
			hipIkBoneName, kneeIkBoneName, legTwistIkBoneName}, false, nil)

	// if fno == 375 {
	// 	motion := vmd.NewVmdMotion(strings.Replace(legIkMotion.Path, "rotate", fmt.Sprintf("leg_ik_1_%s_%04d", direction, fno), -1))
	// 	for _, boneName := range legIkMotion.BoneFrames.GetNames() {
	// 		bf := legIkMotion.BoneFrames.Get(boneName).Get(fno).Copy().(*vmd.BoneFrame)
	// 		bf.Index = 0
	// 		motion.AppendRegisteredBoneFrame(boneName, bf)
	// 	}
	// 	vmd.Write(motion)
	// 	mlog.SetLevel(mlog.DK_VERBOSE)
	// } else {
	// 	mlog.SetLevel(mlog.DEBUG)
	// }

	// 足IK --------------------

	// ひざＩＫは足首の位置を基準とする
	kneeIkBf := vmd.NewBoneFrame(fno)
	ankleOffDelta := legIkOffDeltas.GetByName(ankleBoneName)
	kneeIkBf.Position = ankleOffDelta.GlobalPosition().Subed(legIkModel.Bones.GetByName(kneeIkBoneName).Position)
	legIkMotion.AppendBoneFrame(kneeIkBoneName, kneeIkBf)

	// 足捩ＩＫは足首の位置を基準とする
	legTwistIkBf := vmd.NewBoneFrame(fno)
	legTwistIkBf.Position = ankleOffDelta.GlobalPosition().Subed(kneeIkBf.Position).Subed(legIkModel.Bones.GetByName(legTwistIkBoneName).Position)
	legIkMotion.AppendBoneFrame(legTwistIkBoneName, legTwistIkBf)

	// ももＩＫはひざの位置を基準とする
	hipIkBf := vmd.NewBoneFrame(fno)
	kneeOffDelta := legIkOffDeltas.GetByName(kneeBoneName)
	hipIkBf.Position = kneeOffDelta.GlobalPosition().Subed(kneeIkBf.Position).Subed(legTwistIkBf.Position).Subed(legIkModel.Bones.GetByName(hipIkBoneName).Position)
	legIkMotion.AppendBoneFrame(hipIkBoneName, hipIkBf)

	// if isPrevCopy {
	// 	// 前フレームのコピーの場合、前フレームの値を引き継ぐ
	// 	legBf := vmd.NewBoneFrame(fno)
	// 	prevLegBf := legIkMotion.BoneFrames.Get(legBoneName).Get(fno - 1)
	// 	legBf.Rotation = prevLegBf.Rotation.Copy()
	// 	legIkMotion.AppendRegisteredBoneFrame(legBoneName, legBf)

	// 	kneeBf := vmd.NewBoneFrame(fno)
	// 	prevKneeBf := legIkMotion.BoneFrames.Get(kneeBoneName).Get(fno - 1)
	// 	kneeBf.Rotation = prevKneeBf.Rotation.Copy()
	// 	legIkMotion.AppendRegisteredBoneFrame(kneeBoneName, kneeBf)
	// } else {
	// {
	// _, kneeYZQuat := kneeOffDelta.GlobalRotation().SeparateTwistByAxis(legIkModel.Bones.GetByName(kneeBoneName).NormalizedLocalAxisX)
	kneeBf := vmd.NewBoneFrame(fno)
	// kneeBf.Rotation = mmath.NewMQuaternionFromAxisAngles(mmath.MVec3UnitX, -kneeYZQuat.ToRadian())
	legIkMotion.AppendRegisteredBoneFrame(kneeBoneName, kneeBf)
	// }

	// 足捩はクリア
	hipTwistBf := vmd.NewBoneFrame(fno)
	legIkMotion.AppendBoneFrame(hipTwistBoneName, hipTwistBf)

	// if mlog.DsVerbose() {
	// 	legIkMotion.Path = strings.Replace(prevMotion.Path, "wrist.vmd", direction+"_leg_ik_0.vmd", -1)
	// 	err := vmd.Write(legIkMotion)
	// 	if err != nil {
	// 		mlog.E("Failed to write leg ik vmd: %v", err)
	// 	}
	// }

	loopLimit := 500

	var legIkOnDeltas *vmd.BoneDeltas
	var legQuat, hipTwistQuat, kneeQuat *mmath.MQuaternion
	kneeMinDistance := math.MaxFloat64
	ankleMinDistance := math.MaxFloat64

	// if fno == 377 {
	// 	motion := vmd.NewVmdMotion(strings.Replace(legIkMotion.Path, "rotate", fmt.Sprintf("leg_ik_2_%s_%04d", direction, fno), -1))
	// 	for _, boneName := range legIkMotion.BoneFrames.GetNames() {
	// 		bf := legIkMotion.BoneFrames.Get(boneName).Get(fno).Copy().(*vmd.BoneFrame)
	// 		bf.Index = 0
	// 		motion.AppendRegisteredBoneFrame(boneName, bf)
	// 	}
	// 	vmd.Write(motion)
	// 	mlog.SetLevel(mlog.DK_VERBOSE)
	// } else {
	// 	mlog.SetLevel(mlog.DEBUG)
	// }

legLoop:
	for j := range loopLimit {
		// IKありの変化量を取得
		legIkOnDeltas = legIkMotion.BoneFrames.Deform(fno, legIkModel,
			[]string{hipTwistBoneName, legBoneName, kneeBoneName, ankleBoneName}, true, nil)

		kneeOnDelta := legIkOnDeltas.GetByName(kneeBoneName)
		ankleOnDelta := legIkOnDeltas.GetByName(ankleBoneName)
		kneeDistance := kneeOnDelta.GlobalPosition().Distance(kneeOffDelta.GlobalPosition())
		ankleDistance := ankleOnDelta.GlobalPosition().Distance(ankleOffDelta.GlobalPosition())

		legBf := vmd.NewBoneFrame(fno)
		legBf.Rotation = legIkOnDeltas.GetByName(legBoneName).FrameRotation()
		legIkMotion.AppendRegisteredBoneFrame(legBoneName, legBf)

		kneeBf := vmd.NewBoneFrame(fno)
		kneeBf.Rotation = legIkOnDeltas.GetByName(kneeBoneName).FrameRotation()
		legIkMotion.AppendBoneFrame(kneeBoneName, kneeBf)

		hipTwistBf := vmd.NewBoneFrame(fno)
		hipTwistBf.Rotation = legIkOnDeltas.GetByName(hipTwistBoneName).FrameRotation()
		legIkMotion.AppendBoneFrame(hipTwistBoneName, hipTwistBf)

		mlog.V("[Leg] Distance [%d][%s][%d] knee: %s(%f), ankle: %s(%f), legQuat: %v",
			fno, direction, j, kneeOnDelta.GlobalPosition().String(), kneeDistance, ankleOnDelta.GlobalPosition().String(),
			ankleDistance, legBf.Rotation.ToMMDDegrees())

		if (kneeDistance <= kneeMinDistance && ankleDistance <= ankleMinDistance+0.01) ||
			(kneeDistance <= kneeMinDistance+0.01 && ankleDistance <= ankleMinDistance) {
			mlog.V("** [Leg] Replaced Distance [%d][%s][%d] knee: %f(%f) ankle: %f(%f)",
				fno, direction, j, kneeDistance, kneeMinDistance, ankleDistance, ankleMinDistance)
			kneeMinDistance = kneeDistance
			ankleMinDistance = ankleDistance
			legQuat = legBf.Rotation.Copy()
			hipTwistQuat = hipTwistBf.Rotation.Copy()
			kneeQuat = kneeBf.Rotation.Copy()
		}

		if kneeDistance < 0.01 && ankleDistance < 0.01 {
			mlog.V("*** [Leg] Converged at [%d][%s][%d] knee: %f, ankle: %f", fno, direction, j, kneeDistance, ankleDistance)
			break legLoop
		}
	}

	// 足は足捩りと合成した値を設定
	legBf := vmd.NewBoneFrame(fno)
	legBf.Rotation = legQuat.Muled(hipTwistQuat)
	legIkMotion.AppendRegisteredBoneFrame(legBoneName, legBf)

	// ひざ
	kneeBf = vmd.NewBoneFrame(fno)
	kneeBf.Rotation = kneeQuat
	legIkMotion.AppendRegisteredBoneFrame(kneeBoneName, kneeBf)

	mlog.V("[Leg] FIX Converged at [%d][%s] knee: %f, ankle: %f", fno, direction, kneeMinDistance, ankleMinDistance)

	if kneeMinDistance > 0.3 || ankleMinDistance > 0.3 {
		mlog.D("xxx [Leg] NO FIX Converged at [%d][%s] knee: %f, ankle: %f", fno, direction, kneeMinDistance, ankleMinDistance)

		// 差が大きい場合、キーフレを削除する
		legIkMotion.BoneFrames.Get(legBoneName).Delete(fno)
		legIkMotion.BoneFrames.Get(kneeBoneName).Delete(fno)
	}

	// 足IK結果の変化量を取得
	legOnDeltas := legIkMotion.BoneFrames.Deform(fno, toeIkModel, []string{ankleBoneName, toeBoneName}, false, nil)

	// 足首の位置の差分を取得
	ankleDiffPos := legOnDeltas.GetByName(ankleBoneName).GlobalPosition().Subed(legIkOffDeltas.GetByName(ankleBoneName).GlobalPosition())

	// if mlog.DsVerbose() {
	// 	legIkMotion.Path = strings.Replace(prevMotion.Path, "wrist.vmd", direction+"_leg_ik_1.vmd", -1)
	// 	err := vmd.Write(legIkMotion)
	// 	if err != nil {
	// 		mlog.E("Failed to write leg ik vmd: %v", err)
	// 	}
	// }

	// mlog.SetLevel(mlog.DK_VERBOSE)

	// if mlog.DsIkVerbose() {
	// 	legIkMotion.Path = strings.Replace(prevMotion.Path, "2_rotate.vmd", direction+"_leg_ik_2.vmd", -1)
	// 	err := vmd.Write(legIkMotion)
	// 	if err != nil {
	// 		mlog.E("Failed to write leg ik vmd: %v", err)
	// 	}
	// }

	toeOffPos := legIkOffDeltas.GetByName(toeBoneName).GlobalPosition().Added(ankleDiffPos)
	toeBigOffPos := legIkOffDeltas.GetByName(toeBigBoneName).GlobalPosition().Added(ankleDiffPos)
	toeSmallOffPos := legIkOffDeltas.GetByName(toeSmallBoneName).GlobalPosition().Added(ankleDiffPos)
	heelOffPos := legIkOffDeltas.GetByName(heelBoneName).GlobalPosition().Added(ankleDiffPos)

	// 足首ＩＫはつま先の位置を基準とする
	toeIkBf := vmd.NewBoneFrame(fno)
	toeIkBf.Position = toeOffPos.Subed(toeIkModel.Bones.GetByName(ankleIkBoneName).Position)
	legIkMotion.AppendBoneFrame(ankleIkBoneName, toeIkBf)

	// 足首捩ＩＫはつま先親の位置を基準とする
	ankleTwistIkBf := vmd.NewBoneFrame(fno)
	ankleTwistIkBf.Position = toeBigOffPos.Subed(toeIkBf.Position).Subed(toeIkModel.Bones.GetByName(ankleTwistIkBoneName).Position)
	legIkMotion.AppendBoneFrame(ankleTwistIkBoneName, ankleTwistIkBf)

	// // 足首
	// if isPrevCopy {
	// 	ankleBf := vmd.NewBoneFrame(fno)
	// 	prevAnkleBf := legIkMotion.BoneFrames.Get(ankleBoneName).Get(fno - 1)
	// 	ankleBf.Rotation = prevAnkleBf.Rotation.Copy()
	// 	legIkMotion.AppendRegisteredBoneFrame(ankleBoneName, ankleBf)
	// }

	toeMinDistance := math.MaxFloat64
	toeSmallMinDistance := math.MaxFloat64
	heelMinDistance := math.MaxFloat64
	var ankleQuat, ankleTwistQuat, ankleIkQuat *mmath.MQuaternion

ankleLoop:
	for j := range loopLimit {
		// IKありの変化量を取得
		ikOnDeltas := legIkMotion.BoneFrames.Deform(fno, toeIkModel,
			[]string{ankleBoneName, toeBoneName, toeSmallBoneName, heelBoneName, ankleIkBoneName, ankleTwistBoneName}, true, nil)

		toeOnPos := ikOnDeltas.GetByName(toeBoneName).GlobalPosition()
		toeDistance := toeOnPos.Distance(toeOffPos)
		toeOnSmallPos := ikOnDeltas.GetByName(toeSmallBoneName).GlobalPosition()
		toeSmallDistance := toeOnSmallPos.Distance(toeSmallOffPos)
		heelOnPos := ikOnDeltas.GetByName(heelBoneName).GlobalPosition()
		heelDistance := heelOnPos.Distance(heelOffPos)

		// 足首
		ankleBf := vmd.NewBoneFrame(fno)
		ankleBf.Rotation = ikOnDeltas.GetByName(ankleBoneName).FrameRotation()
		legIkMotion.AppendRegisteredBoneFrame(ankleBoneName, ankleBf)

		// 足首捩
		ankleTwistBf := vmd.NewBoneFrame(fno)
		ankleTwistBf.Rotation = ikOnDeltas.GetByName(ankleTwistBoneName).FrameRotation()
		legIkMotion.AppendBoneFrame(ankleTwistBoneName, ankleTwistBf)

		mlog.V("[Toe] Distance [%d][%s][%d] toe: %f toeSmall: %f heel: %f",
			fno, direction, j, toeDistance, toeSmallDistance, heelDistance)

		if (toeDistance <= toeMinDistance+0.01 && toeSmallDistance <= toeSmallMinDistance && heelDistance <= heelMinDistance) ||
			(toeDistance <= toeMinDistance && toeSmallDistance <= toeSmallMinDistance+0.01 && heelDistance <= heelMinDistance) ||
			(toeDistance <= toeMinDistance && toeSmallDistance <= toeSmallMinDistance && heelDistance <= heelMinDistance+0.01) {
			mlog.V("** [Toe] Replaced Distance [%d][%s][%d] toe: %f(%f) toeSmall: %f(%f) heel: %f(%f)",
				fno, direction, j, toeDistance, toeMinDistance, toeSmallDistance, toeSmallMinDistance, heelDistance, heelMinDistance)

			toeMinDistance = toeDistance
			toeSmallMinDistance = toeSmallDistance
			heelMinDistance = heelDistance

			ankleQuat = ankleBf.Rotation.Copy()
			ankleTwistQuat = ankleTwistBf.Rotation.Copy()
			ankleIkQuat = ikOnDeltas.GetByName(ankleBoneName).LocalMatrix().Quaternion().Inverted()
		}

		if toeDistance < 0.01 && toeSmallDistance < 0.01 && heelDistance < 0.01 {
			mlog.V("*** [Toe] Converged at [%d][%s][%d] toe: %f toeSmall: %f heel: %f", fno, direction, j, toeDistance, toeSmallDistance, heelDistance)
			break ankleLoop
		}
	}

	// 足首
	ankleBf := vmd.NewBoneFrame(fno)
	ankleBf.Rotation = ankleQuat.Muled(ankleTwistQuat)

	mlog.V("[Toe] FIX Converged at [%d][%s] toe: %f, toeSmall: %f, heel: %f", fno, direction, toeMinDistance, toeSmallMinDistance, heelMinDistance)

	if toeMinDistance > 0.3 || toeSmallMinDistance > 0.3 || heelMinDistance > 0.3 {
		mlog.D("xxx [Toe] NO FIX Converged at [%d][%s] toe: %f, toeSmall: %f, heel: %f", fno, direction, toeMinDistance, toeSmallMinDistance, heelMinDistance)

		// 差が大きい場合、キーフレを削除する
		legIkMotion.BoneFrames.Get(ankleBoneName).Delete(fno)
	}

	// 足ＩＫの位置はIK OFF時の足首位置
	legIkBf := vmd.NewBoneFrame(fno)
	legIkBf.Position = ankleOffDelta.GlobalPosition().Subed(toeIkModel.Bones.GetByName(ankleBoneName).Position)
	legIkBf.Rotation = ankleIkQuat
	legIkMotion.AppendRegisteredBoneFrame(legIkBoneName, legIkBf)
}

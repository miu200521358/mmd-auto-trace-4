package usecase

import (
	"fmt"
	"math"
	"strings"
	"sync"

	"github.com/cheggaaa/pb/v3"
	"github.com/miu200521358/mlib_go/pkg/mmath"
	"github.com/miu200521358/mlib_go/pkg/mutils"
	"github.com/miu200521358/mlib_go/pkg/mutils/mlog"
	"github.com/miu200521358/mlib_go/pkg/pmx"
	"github.com/miu200521358/mlib_go/pkg/vmd"
)

func FixGround(allPrevMotions []*vmd.VmdMotion, modelPath string) []*vmd.VmdMotion {
	allGroundMotions := make([]*vmd.VmdMotion, len(allPrevMotions))

	// 全体のタスク数をカウント
	totalFrames := len(allPrevMotions)
	for _, prevMotion := range allPrevMotions {

		minFno := prevMotion.BoneFrames.GetItem("センター").GetMinFrame()
		maxFno := prevMotion.BoneFrames.GetItem("センター").GetMaxFrame()

		totalFrames += int(maxFno-minFno+1.0) * 3
	}

	// モデル読み込み
	pr := &pmx.PmxReader{}
	data, err := pr.ReadByFilepath(modelPath)
	if err != nil {
		mlog.E("Failed to read pmx: %v", err)
	}
	model := data.(*pmx.PmxModel)
	model.SetUp()

	bar := newProgressBar(totalFrames)

	// Create a WaitGroup
	var wg sync.WaitGroup

	// Iterate over allMoveMotions in parallel
	for i, prevMotion := range allPrevMotions {
		// Increment the WaitGroup counter
		wg.Add(1)

		go func(i int, prevMotion *vmd.VmdMotion) {
			defer wg.Done()
			allGroundMotions[i] = setGroundedFootMotion(model, prevMotion, i, bar)
		}(i, prevMotion)
	}

	wg.Wait()
	bar.Finish()

	return allGroundMotions
}

func setGroundedFootMotion(model *pmx.PmxModel, motion *vmd.VmdMotion, i int, bar *pb.ProgressBar) *vmd.VmdMotion {
	motion.Path = strings.Replace(motion.Path, "_arm_ik.vmd", "_ground.vmd", -1)
	motion.SetName(fmt.Sprintf("MAT4 Ground %02d", i+1))

	minFno := motion.BoneFrames.GetItem("センター").GetMinFrame()
	maxFno := motion.BoneFrames.GetItem("センター").GetMaxFrame()

	legIkYs := make([]float64, 0, int(maxFno)-int(minFno)+1)

	for fno := minFno; fno <= maxFno; fno += 1.0 {
		bar.Increment()

		leftY := motion.BoneFrames.Data[pmx.LEG_IK.Left()].Data[float32(fno)].Position.GetY()
		rightY := motion.BoneFrames.Data[pmx.LEG_IK.Right()].Data[float32(fno)].Position.GetY()

		mlog.V("fno: %d, left: %f, right: %f", int(fno), leftY, rightY)

		legIkYs = append(legIkYs, min(leftY, rightY))
	}

	// 足ＩＫ-Y値全体の9割の場所を接地点とする
	groundY := percentile(legIkYs, 0.9)
	mlog.V("groundY: %f", groundY)

	for fno := minFno; fno <= maxFno; fno += 1.0 {
		bar.Increment()

		newLeftY := motion.BoneFrames.Data[pmx.LEG_IK.Left()].Data[float32(fno)].Position.GetY() - groundY
		newRightY := motion.BoneFrames.Data[pmx.LEG_IK.Right()].Data[float32(fno)].Position.GetY() - groundY

		newMinY := min(newLeftY, newRightY)

		frameGroundY := groundY
		if newMinY < 0.0 {
			frameGroundY += newMinY
		}

		newLeftY = motion.BoneFrames.Data[pmx.LEG_IK.Left()].Data[float32(fno)].Position.GetY() - frameGroundY
		if newLeftY < 0.2 {
			newLeftY = 0.0
		}
		newRightY = motion.BoneFrames.Data[pmx.LEG_IK.Right()].Data[float32(fno)].Position.GetY() - frameGroundY
		if newRightY < 0.2 {
			newRightY = 0.0
		}

		motion.BoneFrames.Data[pmx.LEG_IK.Left()].Data[float32(fno)].Position.SetY(newLeftY)
		motion.BoneFrames.Data[pmx.LEG_IK.Right()].Data[float32(fno)].Position.SetY(newRightY)
		motion.BoneFrames.Data[pmx.CENTER.String()].Data[float32(fno)].Position.SetY(
			motion.BoneFrames.Data[pmx.CENTER.String()].Data[float32(fno)].Position.GetY() - frameGroundY)
	}

	for fno := minFno; fno <= maxFno; fno += 1.0 {
		bar.Increment()

		// IFをONにした状態での位置関係を取得
		deltas := motion.AnimateBone(float32(fno), model, []string{
			"左つま先親",
			"左つま先子",
			"左かかと",
			"右つま先親",
			"右つま先子",
			"右かかと",
			pmx.TOE.Left(),
			pmx.TOE.Right(),
			pmx.ANKLE.Left(),
			pmx.ANKLE.Right(),
			pmx.LEG_IK.Left(),
			pmx.LEG_IK.Right(),
		}, true)

		// Yが0の場合、足首の向きを調整して接地させる
		for _, direction := range []string{"右", "左"} {
			heelBoneName := fmt.Sprintf("%sかかと", direction)
			toeBoneName := pmx.TOE.StringFromDirection(direction)
			toeBigBoneName := fmt.Sprintf("%sつま先親", direction)
			toeSmallBoneName := fmt.Sprintf("%sつま先子", direction)
			ankleBoneName := pmx.ANKLE.StringFromDirection(direction)
			legIkBoneName := pmx.LEG_IK.StringFromDirection(direction)

			if motion.BoneFrames.Data[legIkBoneName].Data[float32(fno)].Position.GetY() == 0.0 {
				heelPos := deltas.GetItem(heelBoneName, float32(fno)).Position
				toePos := deltas.GetItem(toeBoneName, float32(fno)).Position
				toeHorizontalPos := mmath.MVec3{toePos.GetX(), heelPos.GetY(), toePos.GetZ()}

				toeLocalPos := toePos.Subed(heelPos).Normalize()
				toeHorizontalLocalPos := toeHorizontalPos.Subed(heelPos).Normalize()

				// 縦方向の回転角
				ankleVRad := math.Acos(mmath.ClampFloat(toeLocalPos.Dot(toeHorizontalLocalPos), -1.0, 1.0))
				// 縦方向の回転軸
				ankleVAxis := toeLocalPos.Cross(toeHorizontalLocalPos).Normalize()
				// 縦方向の回転角度
				ankleVQuat := mmath.NewMQuaternionFromAxisAngles(ankleVAxis, ankleVRad)

				// -----------

				toeBigPos := deltas.GetItem(toeBigBoneName, float32(fno)).Position
				toeSmallPos := deltas.GetItem(toeSmallBoneName, float32(fno)).Position
				toeSmallHorizontalPos := mmath.MVec3{toeSmallPos.GetX(), toeBigPos.GetY(), toeSmallPos.GetZ()}

				toeSmallLocalPos := toeSmallPos.Subed(toeBigPos).Normalize()
				toeSmallHorizontalLocalPos := toeSmallHorizontalPos.Subed(toeBigPos).Normalize()

				// 横方向の回転角
				ankleHRad := math.Acos(mmath.ClampFloat(toeSmallLocalPos.Dot(toeSmallHorizontalLocalPos), -1.0, 1.0))
				// 横方向の回転軸
				ankleHAxis := toeSmallLocalPos.Cross(toeSmallHorizontalLocalPos).Normalize()
				// 横方向の回転角度
				ankleHQuat := mmath.NewMQuaternionFromAxisAngles(ankleHAxis, ankleHRad)

				// 足首の向きを調整する角度
				ankleQuat := ankleHQuat.Muled(ankleVQuat).Muled(motion.BoneFrames.Data[ankleBoneName].Data[float32(fno)].Rotation.GetQuaternion())
				motion.BoneFrames.Data[ankleBoneName].Data[float32(fno)].Rotation.SetQuaternion(ankleQuat)

				// 足ＩＫの向きを調整する角度
				legIkQuat := ankleHQuat.Muled(ankleVQuat).Muled(motion.BoneFrames.Data[legIkBoneName].Data[float32(fno)].Rotation.GetQuaternion())
				motion.BoneFrames.Data[legIkBoneName].Data[float32(fno)].Rotation.SetQuaternion(legIkQuat)
			}
		}

	}

	if mlog.IsDebug() {
		motion.Path = strings.Replace(motion.Path, "_arm_ik.vmd", "_ground.vmd", -1)
		err := vmd.Write(motion)
		if err != nil {
			mlog.E("Failed to write ground vmd: %v", err)
		}
	}

	return motion
}

func percentile(values []float64, percent float64) float64 {
	mutils.SortFloat64s(values)

	// percentに応じた中央値を取得
	middle := int(float64(len(values)) * percent)
	median := values[middle]
	if len(values)%2 == 0 {
		median = (values[middle-1] + values[middle]) / 2
	}

	return median
}
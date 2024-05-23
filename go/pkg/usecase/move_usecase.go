package usecase

import (
	"math"
	"strings"

	"github.com/miu200521358/mlib_go/pkg/mutils/mlog"
	"github.com/miu200521358/mlib_go/pkg/pmx"
	"github.com/miu200521358/mlib_go/pkg/vmd"

	"github.com/miu200521358/mmd-auto-trace-4/pkg/model"
	"github.com/miu200521358/mmd-auto-trace-4/pkg/utils"
)

const RATIO = 1 / 0.09

func Move(frames *model.Frames, motionNum, allNum int) *vmd.VmdMotion {
	mlog.I("[%d/%d] Convert Move ...", motionNum, allNum)

	minFno := getMinFrame(frames.Frames)
	minFrame := frames.Frames[minFno]
	rootPos := model.Position{X: minFrame.Camera.X, Y: minFrame.Camera.Y, Z: minFrame.Camera.Z}

	bar := utils.NewProgressBar(len(frames.Frames))

	movMotion := vmd.NewVmdMotion(strings.Replace(frames.Path, "_smooth.json", "_move.vmd", -1))

	for fno, frame := range frames.Frames {
		bar.Increment()

		if frame.Confidential < 0.8 {
			continue
		}

		for jointName, pos := range frame.Joint3D {
			// ボーン名がある場合、ボーン移動モーションにも出力
			if boneName, ok := joint2bones[string(jointName)]; ok {
				bf := vmd.NewBoneFrame(fno)
				bf.Position.SetX(pos.X * RATIO)
				bf.Position.SetY(pos.Y * RATIO)
				bf.Position.SetZ(-pos.Z * RATIO)
				movMotion.AppendRegisteredBoneFrame(boneName, bf)
			}
		}

		{
			bf := vmd.NewBoneFrame(fno)
			bf.Position.SetX(frame.Camera.X * RATIO)
			bf.Position.SetY(frame.Camera.Y * RATIO)
			bf.Position.SetZ(-(frame.Camera.Z - rootPos.Z) * 0.5)
			movMotion.AppendRegisteredBoneFrame("Camera", bf)
		}

		{
			// 追加で計算するボーン
			{
				bf := vmd.NewBoneFrame(fno)
				bf.Position = movMotion.BoneFrames.Get(pmx.LEG.Right()).Get(fno).Position.Added(movMotion.BoneFrames.Get(pmx.LEG.Left()).Get(fno).Position).DivedScalar(2)
				movMotion.AppendRegisteredBoneFrame("下半身先", bf)
			}
			{
				bf := vmd.NewBoneFrame(fno)
				bf.Position = movMotion.BoneFrames.Get(pmx.NECK.String()).Get(fno).Position.Added(
					movMotion.BoneFrames.Get(pmx.ARM.Left()).Get(fno).Position.Subed(movMotion.BoneFrames.Get(pmx.NECK.String()).Get(fno).Position).DivedScalar(2))
				movMotion.AppendRegisteredBoneFrame(pmx.SHOULDER.Left(), bf)
			}
			{
				bf := vmd.NewBoneFrame(fno)
				bf.Position = movMotion.BoneFrames.Get(pmx.NECK.String()).Get(fno).Position.Added(
					movMotion.BoneFrames.Get(pmx.ARM.Right()).Get(fno).Position.Subed(movMotion.BoneFrames.Get(pmx.NECK.String()).Get(fno).Position).DivedScalar(2))
				movMotion.AppendRegisteredBoneFrame(pmx.SHOULDER.Right(), bf)
			}
			{
				bf := vmd.NewBoneFrame(fno)
				bf.Position = movMotion.BoneFrames.Get("左つま先親").Get(fno).Position.Added(movMotion.BoneFrames.Get("左つま先子").Get(fno).Position).DivedScalar(2)
				movMotion.AppendRegisteredBoneFrame("左つま先", bf)
			}
			{
				bf := vmd.NewBoneFrame(fno)
				bf.Position = movMotion.BoneFrames.Get("右つま先親").Get(fno).Position.Added(movMotion.BoneFrames.Get("右つま先子").Get(fno).Position).DivedScalar(2)
				movMotion.AppendRegisteredBoneFrame("右つま先", bf)
			}
		}
	}

	bar.Finish()

	return movMotion
}

func getMinFrame(m map[int]model.Frame) int {
	minFrame := math.MaxInt

	for frame := range m {
		if frame < minFrame {
			minFrame = frame
		}
	}

	return minFrame
}

var joint2bones = map[string]string{
	"OP Nose":       "鼻",     // 0
	"OP Neck":       "首",     // 1
	"OP RShoulder":  "右腕",    // 2
	"OP RElbow":     "右ひじ",   // 3
	"OP RWrist":     "右手首",   // 4
	"OP LShoulder":  "左腕",    // 5
	"OP LElbow":     "左ひじ",   // 6
	"OP LWrist":     "左手首",   // 7
	"OP MidHip":     "下半身",   // 8
	"OP RHip":       "右足",    // 9
	"OP RKnee":      "右ひざ",   // 10
	"OP RAnkle":     "右足首",   // 11
	"OP LHip":       "左足",    // 12
	"OP LKnee":      "左ひざ",   // 13
	"OP LAnkle":     "左足首",   // 14
	"OP REye":       "右目",    // 15
	"OP LEye":       "左目",    // 16
	"OP REar":       "右耳",    // 17
	"OP LEar":       "左耳",    // 18
	"OP LBigToe":    "左つま先親", // 19
	"OP LSmallToe":  "左つま先子", // 20
	"OP LHeel":      "左かかと",  // 21
	"OP RBigToe":    "右つま先親", // 22
	"OP RSmallToe":  "右つま先子", // 23
	"OP RHeel":      "右かかと",  // 24
	"Pelvis (MPII)": "上半身",   // 39
	"Spine (H36M)":  "上半身2",  // 41
	"Head (H36M)":   "頭",     // 43
	"Pelvis2":       "下半身先",
}

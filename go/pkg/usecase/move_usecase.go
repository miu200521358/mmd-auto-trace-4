package usecase

import (
	"fmt"
	"math"
	"strings"
	"sync"

	"github.com/miu200521358/mlib_go/pkg/mutils/mlog"
	"github.com/miu200521358/mlib_go/pkg/pmx"
	"github.com/miu200521358/mlib_go/pkg/vmd"

	"github.com/miu200521358/mmd-auto-trace-4/pkg/model"
)

const RATIO = 1 / 0.09

func Move(allFrames []*model.Frames) ([]*vmd.VmdMotion, []*vmd.VmdMotion) {
	mlog.I("Start: Move =============================")

	allMoveMotions := make([]*vmd.VmdMotion, len(allFrames))
	allMpMoveMotions := make([]*vmd.VmdMotion, len(allFrames))

	minFno := getMinFrame(allFrames[0].Frames)
	minFrame := allFrames[0].Frames[minFno]
	rootPos := model.Position{X: minFrame.Camera.X, Y: minFrame.Camera.Y, Z: minFrame.Camera.Z}

	// 全体のタスク数をカウント
	totalFrames := len(allFrames)
	for _, frames := range allFrames {
		totalFrames += len(frames.Frames)
	}

	bar := newProgressBar(totalFrames)

	// Create a WaitGroup
	var wg sync.WaitGroup

	// Iterate over allFrames in parallel
	for i, frames := range allFrames {
		// Increment the WaitGroup counter
		wg.Add(1)

		go func(i int, frames *model.Frames) {
			defer wg.Done()
			defer mlog.I("[%d/%d] Convert Move ...", i, len(allFrames))

			movMotion := vmd.NewVmdMotion(strings.Replace(frames.Path, "_smooth.json", "_move.vmd", -1))
			movMotion.SetName(fmt.Sprintf("MAT4 Move %02d", i+1))

			mpMovMotion := vmd.NewVmdMotion(strings.Replace(frames.Path, "_smooth.json", "_mp-move.vmd", -1))
			mpMovMotion.SetName(fmt.Sprintf("MAT4 Move %02d", i+1))

			jointMotion := vmd.NewVmdMotion(strings.Replace(frames.Path, "_smooth.json", "_joint-move.vmd", -1))
			jointMotion.SetName(fmt.Sprintf("MAT4 Joint Move %02d", i+1))

			for fno, frame := range frames.Frames {
				bar.Increment()

				if frame.Confidential < 0.8 {
					continue
				}

				for jointName, pos := range frame.Joint3D {
					// 4D-Humansのジョイント移動モーション出力
					bf := vmd.NewBoneFrame(float32(fno))
					bf.Position.SetX(pos.X * RATIO)
					bf.Position.SetY(pos.Y * RATIO)
					bf.Position.SetZ(pos.Z * RATIO)
					jointMotion.AppendRegisteredBoneFrame(string(jointName), bf)

					// ボーン名がある場合、ボーン移動モーションにも出力
					if boneName, ok := joint2bones[string(jointName)]; ok {
						bf := vmd.NewBoneFrame(float32(fno))
						bf.Position.SetX(pos.X * RATIO)
						bf.Position.SetY(pos.Y * RATIO)
						bf.Position.SetZ(pos.Z * RATIO)
						movMotion.AppendRegisteredBoneFrame(boneName, bf)
					}
				}

				{
					bf := vmd.NewBoneFrame(float32(fno))
					bf.Position.SetX(frame.Camera.X * RATIO)
					bf.Position.SetY(frame.Camera.Y * RATIO)
					bf.Position.SetZ((frame.Camera.Z - rootPos.Z) * 0.5)
					jointMotion.AppendRegisteredBoneFrame("Camera", bf)
				}
				{
					bf := vmd.NewBoneFrame(float32(fno))
					bf.Position.SetX(frame.Camera.X * RATIO)
					bf.Position.SetY(frame.Camera.Y * RATIO)
					bf.Position.SetZ((frame.Camera.Z - rootPos.Z) * 0.5)
					movMotion.AppendRegisteredBoneFrame("Camera", bf)
				}

				{
					// 追加で計算するボーン
					{
						bf := vmd.NewBoneFrame(float32(fno))
						bf.Position = movMotion.BoneFrames.GetItem(pmx.LEG.Right()).GetItem(float32(fno)).Position.Added(movMotion.BoneFrames.GetItem(pmx.LEG.Left()).GetItem(float32(fno)).Position).DivedScalar(2)
						movMotion.AppendRegisteredBoneFrame("下半身先", bf)
					}
					{
						bf := vmd.NewBoneFrame(float32(fno))
						bf.Position = movMotion.BoneFrames.GetItem(pmx.NECK.String()).GetItem(float32(fno)).Position.Added(
							movMotion.BoneFrames.GetItem(pmx.ARM.Left()).GetItem(float32(fno)).Position.Subed(movMotion.BoneFrames.GetItem(pmx.NECK.String()).GetItem(float32(fno)).Position).DivedScalar(2))
						movMotion.AppendRegisteredBoneFrame(pmx.SHOULDER.Left(), bf)
					}
					{
						bf := vmd.NewBoneFrame(float32(fno))
						bf.Position = movMotion.BoneFrames.GetItem(pmx.NECK.String()).GetItem(float32(fno)).Position.Added(
							movMotion.BoneFrames.GetItem(pmx.ARM.Right()).GetItem(float32(fno)).Position.Subed(movMotion.BoneFrames.GetItem(pmx.NECK.String()).GetItem(float32(fno)).Position).DivedScalar(2))
						movMotion.AppendRegisteredBoneFrame(pmx.SHOULDER.Right(), bf)
					}
					{
						bf := vmd.NewBoneFrame(float32(fno))
						bf.Position = movMotion.BoneFrames.GetItem("左つま先親").GetItem(float32(fno)).Position.Added(movMotion.BoneFrames.GetItem("左つま先子").GetItem(float32(fno)).Position).DivedScalar(2)
						movMotion.AppendRegisteredBoneFrame("左つま先", bf)
					}
					{
						bf := vmd.NewBoneFrame(float32(fno))
						bf.Position = movMotion.BoneFrames.GetItem("右つま先親").GetItem(float32(fno)).Position.Added(movMotion.BoneFrames.GetItem("右つま先子").GetItem(float32(fno)).Position).DivedScalar(2)
						movMotion.AppendRegisteredBoneFrame("右つま先", bf)
					}
				}

				for jointName, posVis := range frame.Mediapipe {
					// mediapipeのジョイント移動モーション出力
					// ボーン名がある場合、ボーン移動モーションにも出力
					if boneName, ok := mpJoint2bones[string(jointName)]; ok {
						bf := vmd.NewBoneFrame(float32(fno))
						bf.Position.SetX(posVis.X)
						bf.Position.SetY(posVis.Y)
						bf.Position.SetZ(posVis.Z)
						mpMovMotion.AppendRegisteredBoneFrame(boneName, bf)
					}
				}

				{
					// 追加で計算するボーン
					{
						bf := vmd.NewBoneFrame(float32(fno))
						bf.Position = mpMovMotion.BoneFrames.GetItem(pmx.LEG.Right()).GetItem(float32(fno)).Position.Added(mpMovMotion.BoneFrames.GetItem(pmx.LEG.Left()).GetItem(float32(fno)).Position).DivedScalar(2)
						mpMovMotion.AppendRegisteredBoneFrame(pmx.UPPER.String(), bf)
					}
					{
						bf := vmd.NewBoneFrame(float32(fno))
						bf.Position = mpMovMotion.BoneFrames.GetItem(pmx.ARM.Right()).GetItem(float32(fno)).Position.Added(mpMovMotion.BoneFrames.GetItem(pmx.ARM.Left()).GetItem(float32(fno)).Position).DivedScalar(2)
						mpMovMotion.AppendRegisteredBoneFrame(pmx.NECK.String(), bf)
					}
					{
						bf := vmd.NewBoneFrame(float32(fno))
						bf.Position = mpMovMotion.BoneFrames.GetItem(pmx.UPPER.String()).GetItem(float32(fno)).Position.Added(
							mpMovMotion.BoneFrames.GetItem(pmx.NECK.String()).GetItem(float32(fno)).Position.Subed(mpMovMotion.BoneFrames.GetItem(pmx.UPPER.String()).GetItem(float32(fno)).Position).DivedScalar(2),
						)
						mpMovMotion.AppendRegisteredBoneFrame(pmx.UPPER.String(), bf)
					}
					{
						bf := vmd.NewBoneFrame(float32(fno))
						bf.Position = mpMovMotion.BoneFrames.GetItem(pmx.NECK.String()).GetItem(float32(fno)).Position.Added(
							mpMovMotion.BoneFrames.GetItem(pmx.ARM.Left()).GetItem(float32(fno)).Position.Subed(mpMovMotion.BoneFrames.GetItem(pmx.NECK.String()).GetItem(float32(fno)).Position).DivedScalar(2))
						mpMovMotion.AppendRegisteredBoneFrame(pmx.SHOULDER.Left(), bf)
					}
					{
						bf := vmd.NewBoneFrame(float32(fno))
						bf.Position = mpMovMotion.BoneFrames.GetItem(pmx.NECK.String()).GetItem(float32(fno)).Position.Added(
							mpMovMotion.BoneFrames.GetItem(pmx.ARM.Right()).GetItem(float32(fno)).Position.Subed(mpMovMotion.BoneFrames.GetItem(pmx.NECK.String()).GetItem(float32(fno)).Position).DivedScalar(2))
						mpMovMotion.AppendRegisteredBoneFrame(pmx.SHOULDER.Right(), bf)
					}
				}

			}

			if mlog.IsDebug() {
				err := vmd.Write(jointMotion)
				if err != nil {
					mlog.E("Failed to write joint vmd: %v", err)
				}
			}

			err := vmd.Write(movMotion)
			if err != nil {
				mlog.E("Failed to write move vmd: %v", err)
			}

			err = vmd.Write(mpMovMotion)
			if err != nil {
				mlog.E("Failed to write mp move vmd: %v", err)
			}

			allMoveMotions[i] = movMotion
			allMpMoveMotions[i] = mpMovMotion
		}(i, frames)
	}

	wg.Wait()
	bar.Finish()

	mlog.I("End: Move =============================")

	return allMoveMotions, allMpMoveMotions
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

var mpJoint2bones = map[string]string{
	"left shoulder":  "左腕",
	"right shoulder": "右腕",
	"left elbow":     "左ひじ",
	"right elbow":    "右ひじ",
	"left wrist":     "左手首",
	"right wrist":    "右手首",
	"left pinky":     "左小指１",
	"right pinky":    "右小指１",
	"left index":     "左人指先",
	"right index":    "右人指先",
	"left thumb":     "左親指１",
	"right thumb":    "右親指１",
	"left hip":       "左足",
	"right hip":      "右足",
}

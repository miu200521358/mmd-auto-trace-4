package usecase

import (
	"fmt"
	"math"
	"strings"
	"sync"

	"github.com/cheggaaa/pb/v3"

	"github.com/miu200521358/mlib_go/pkg/deform"
	"github.com/miu200521358/mlib_go/pkg/mutils/mlog"
	"github.com/miu200521358/mlib_go/pkg/vmd"

	"github.com/miu200521358/mmd-auto-trace-4/pkg/model"
)

const RATIO = 1 / 0.09

func Move(allFrames []*model.Frames) []*vmd.VmdMotion {
	allMoveMotions := make([]*vmd.VmdMotion, len(allFrames))

	minFno := getMinFrame(allFrames[0].Frames)
	minFrame := allFrames[0].Frames[minFno]
	rootPos := model.Position{X: minFrame.Camera.X, Y: minFrame.Camera.Y, Z: minFrame.Camera.Z}

	// 全体のタスク数をカウント
	totalFrames := len(allFrames) * 2

	bar := pb.StartNew(totalFrames)

	// Create a WaitGroup
	var wg sync.WaitGroup

	// Iterate over allFrames in parallel
	for i, frames := range allFrames {
		// Increment the WaitGroup counter
		wg.Add(1)

		go func(i int, frames *model.Frames) {
			defer wg.Done()
			defer bar.Increment()

			movMotion := vmd.NewVmdMotion(strings.Replace(frames.Path, "_smooth.json", "_smooth_mov.vmd", -1))
			movMotion.SetName(fmt.Sprintf("MAT4 Move %02d", i+1))

			jointMotion := vmd.NewVmdMotion(strings.Replace(frames.Path, "_smooth.json", "_smooth_joint_mov.vmd", -1))
			jointMotion.SetName(fmt.Sprintf("MAT4 Joint Move %02d", i+1))

			for fno, frame := range frames.Frames {
				for jointName, pos := range frame.Joint3D {
					// ジョイント移動モーション出力
					bf := deform.NewBoneFrame(float32(fno))
					bf.Registered = true
					bf.Position.SetX(pos.X * RATIO)
					bf.Position.SetY(pos.Y * RATIO)
					bf.Position.SetZ(pos.Z * RATIO)
					jointMotion.AppendBoneFrame(string(jointName), bf)

					// ボーン名がある場合、ボーン移動モーションにも出力
					if boneName, ok := joint2bones[string(jointName)]; ok {
						bf := deform.NewBoneFrame(float32(fno))
						bf.Registered = true
						bf.Position.SetX(pos.X * RATIO)
						bf.Position.SetY(pos.Y * RATIO)
						bf.Position.SetZ(pos.Z * RATIO)
						movMotion.AppendBoneFrame(boneName, bf)
					}
				}

				{
					bf := deform.NewBoneFrame(float32(fno))
					bf.Registered = true
					bf.Position.SetX(frame.Camera.X * RATIO)
					bf.Position.SetY(frame.Camera.Y * RATIO)
					bf.Position.SetZ((frame.Camera.Z - rootPos.Z))
					jointMotion.AppendBoneFrame("Camera", bf)
				}
				{
					bf := deform.NewBoneFrame(float32(fno))
					bf.Registered = true
					bf.Position.SetX(frame.Camera.X * RATIO)
					bf.Position.SetY(frame.Camera.Y * RATIO)
					bf.Position.SetZ((frame.Camera.Z - rootPos.Z))
					movMotion.AppendBoneFrame("Camera", bf)
				}

				{
					// 追加で計算するボーン
					{
						bf := deform.NewBoneFrame(float32(fno))
						bf.Registered = true
						bf.Position = movMotion.BoneFrames.GetItem("右足").GetItem(float32(fno)).Position.Added(movMotion.BoneFrames.GetItem("左足").GetItem(float32(fno)).Position).DivedScalar(2)
						movMotion.AppendBoneFrame("下半身先", bf)
					}
					{
						bf := deform.NewBoneFrame(float32(fno))
						bf.Registered = true
						bf.Position = movMotion.BoneFrames.GetItem("首").GetItem(float32(fno)).Position.Added(movMotion.BoneFrames.GetItem("左腕").GetItem(float32(fno)).Position).DivedScalar(2)
						movMotion.AppendBoneFrame("左肩", bf)
					}
					{
						bf := deform.NewBoneFrame(float32(fno))
						bf.Registered = true
						bf.Position = movMotion.BoneFrames.GetItem("首").GetItem(float32(fno)).Position.Added(movMotion.BoneFrames.GetItem("右腕").GetItem(float32(fno)).Position).DivedScalar(2)
						movMotion.AppendBoneFrame("右肩", bf)
					}
					{
						bf := deform.NewBoneFrame(float32(fno))
						bf.Registered = true
						bf.Position = movMotion.BoneFrames.GetItem("左つま先親").GetItem(float32(fno)).Position.Added(movMotion.BoneFrames.GetItem("左つま先子").GetItem(float32(fno)).Position).DivedScalar(2)
						movMotion.AppendBoneFrame("左つま先", bf)
					}
					{
						bf := deform.NewBoneFrame(float32(fno))
						bf.Registered = true
						bf.Position = movMotion.BoneFrames.GetItem("右つま先親").GetItem(float32(fno)).Position.Added(movMotion.BoneFrames.GetItem("右つま先子").GetItem(float32(fno)).Position).DivedScalar(2)
						movMotion.AppendBoneFrame("右つま先", bf)
					}
				}
			}

			err := vmd.Write(jointMotion)
			if err != nil {
				mlog.E("Failed to write joint vmd: %v", err)
			}
			bar.Increment()

			// err = vmd.Write(movMotion)
			// if err != nil {
			// 	mlog.E("Failed to write move vmd: %v", err)
			// }
			// bar.Increment()

			allMoveMotions[i] = movMotion
		}(i, frames)
	}

	wg.Wait()
	bar.Finish()

	return allMoveMotions
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

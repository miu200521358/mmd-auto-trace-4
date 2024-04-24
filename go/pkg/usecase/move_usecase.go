package usecase

import (
	"fmt"
	"strings"

	"github.com/miu200521358/mlib_go/pkg/deform"
	"github.com/miu200521358/mlib_go/pkg/vmd"

	"github.com/miu200521358/mmd-auto-trace-4/pkg/model"

)

const RATIO = 1 / 0.09

func Move(allFrames []*model.Frames) []*vmd.VmdMotion {
	var allMoveMotions []*vmd.VmdMotion
	var rootPos model.Position

rootLoop:
	for _, frames := range allFrames {
		for _, frame := range frames.Frames {
			// 最初の人物の最初のフレームのカメラ位置をrootとする
			rootPos = model.Position{X: frame.Camera.X, Y: frame.Camera.Y, Z: frame.Camera.Z}
			break rootLoop
		}
	}

	// Create a channel to receive the results
	resultCh := make(chan *vmd.VmdMotion)

	// Iterate over allFrames in parallel
	for i, frames := range allFrames {
		go func(i int, frames *model.Frames) {
			movMotion := vmd.NewVmdMotion(strings.Replace(frames.Path, ".json", "_mov.vmd", -1))
			movMotion.SetName(fmt.Sprintf("MAT4 Move %02d", i+1))

			for fno, frame := range frames.Frames {
				for jointName, pos := range frame.Joint3D {
					// ボーンの位置を移動
					bf := deform.NewBoneFrame(float32(fno))
					bf.Registered = true
					bf.Position.SetX(pos.X * RATIO)
					bf.Position.SetY(pos.Y * RATIO)
					bf.Position.SetZ(pos.Z * RATIO)
					movMotion.AppendBoneFrame(string(jointName), bf)
				}

				{
					bf := deform.NewBoneFrame(float32(fno))
					bf.Registered = true
					bf.Position.SetX(frame.Camera.X * RATIO)
					bf.Position.SetY(frame.Camera.Y * RATIO)
					bf.Position.SetZ((frame.Camera.Z - rootPos.Z))
					movMotion.AppendBoneFrame("Camera", bf)
				}
			}

			// Send the result to the channel
			resultCh <- movMotion
		}(i, frames)
	}

	// Collect the results from the channel
	for range allFrames {
		movMotion := <-resultCh
		allMoveMotions = append(allMoveMotions, movMotion)
	}

	// Close the channel
	close(resultCh)

	return allMoveMotions
}

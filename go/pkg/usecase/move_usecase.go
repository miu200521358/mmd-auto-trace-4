package usecase

import (
	"github.com/miu200521358/mlib_go/pkg/deform"
	"github.com/miu200521358/mlib_go/pkg/vmd"

	"github.com/miu200521358/mmd-auto-trace-4/pkg/model"
)

func Move(frames *model.Frames) {
	movMotion := vmd.NewVmdMotion("")

	for fno, frame := range frames.Frames {
		for jointName, pos := range frame.Joint3D.Position {
			// ボーンの位置を移動
			bf := deform.NewBoneFrame(float32(fno))
			bf.Position.SetX(pos.X)
			bf.Position.SetY(pos.Y)
			bf.Position.SetZ(pos.Z)
			movMotion.AppendBoneFrame(string(jointName), bf)
		}

		{
			bf := deform.NewBoneFrame(float32(fno))
			bf.Position.SetX(frame.Camera[0])
			bf.Position.SetY(frame.Camera[1])
			bf.Position.SetZ(frame.Camera[2])
		}
	}
}

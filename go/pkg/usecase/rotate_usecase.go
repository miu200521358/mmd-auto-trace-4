package usecase

import (
	"fmt"
	"strings"
	"sync"

	"github.com/cheggaaa/pb/v3"

	"github.com/miu200521358/mlib_go/pkg/deform"
	"github.com/miu200521358/mlib_go/pkg/mmath"
	"github.com/miu200521358/mlib_go/pkg/mutils/mlog"
	"github.com/miu200521358/mlib_go/pkg/pmx"
	"github.com/miu200521358/mlib_go/pkg/vmd"
)

func Rotate(allMoveMotions []*vmd.VmdMotion, modelPath string) []*vmd.VmdMotion {
	var allRotateMotions []*vmd.VmdMotion

	// 全体のタスク数をカウント
	totalFrames := 0
	for _, movMotion := range allMoveMotions {
		totalFrames += int(movMotion.GetMaxFrame())
	}

	// モデル読み込み
	pr := &pmx.PmxReader{}
	data, err := pr.ReadByFilepath(modelPath)
	if err != nil {
		mlog.E("Failed to read pmx: %v", err)
	}
	model := data.(*pmx.PmxModel)

	bar := pb.StartNew(totalFrames)

	// Create a WaitGroup
	var wg sync.WaitGroup

	// Iterate over allMoveMotions in parallel
	for i, movMotion := range allMoveMotions {
		// Increment the WaitGroup counter
		wg.Add(1)

		go func(i int, movMotion *vmd.VmdMotion) {
			defer wg.Done()

			rotMotion := vmd.NewVmdMotion(strings.Replace(movMotion.Path, "_mov.vmd", "_rot.vmd", -1))
			rotMotion.SetName(fmt.Sprintf("MAT4 Rot %02d", i+1))

			for fno := range movMotion.BoneFrames.GetItem("Camera").RegisteredIndexes {
				{
					bf := deform.NewBoneFrame(float32(fno))
					bf.Registered = true
					bf.Position = movMotion.BoneFrames.GetItem("Camera").GetItem(float32(fno)).Position
					rotMotion.AppendBoneFrame("センター", bf)
				}
			}

			for _, boneConfig := range boneConfigs {
				for fno := range movMotion.BoneFrames.GetItem(boneConfig.Name).RegisteredIndexes {
					bar.Increment()

					// モデルのボーン角度
					boneDirectionFrom := model.Bones.GetItemByName(boneConfig.DirectionFrom).Position
					boneDirectionTo := model.Bones.GetItemByName(boneConfig.DirectionTo).Position
					boneUpFrom := model.Bones.GetItemByName(boneConfig.UpFrom).Position
					boneUpTo := model.Bones.GetItemByName(boneConfig.UpTo).Position

					boneDirectionVector := boneDirectionTo.Subed(boneDirectionFrom).Normalize()
					boneUpVector := boneUpTo.Subed(boneUpFrom).Normalize()
					boneCrossVector := boneUpVector.Cross(boneDirectionVector).Normalize()

					boneQuat := mmath.NewMQuaternionFromDirection(boneDirectionVector, boneCrossVector)

					// モーションのボーン角度
					motionDirectionFromPos := movMotion.BoneFrames.GetItem(boneConfig.DirectionFrom).GetItem(float32(fno)).Position
					motionDirectionToPos := movMotion.BoneFrames.GetItem(boneConfig.DirectionTo).GetItem(float32(fno)).Position
					motionUpFromPos := movMotion.BoneFrames.GetItem(boneConfig.UpFrom).GetItem(float32(fno)).Position
					motionUpToPos := movMotion.BoneFrames.GetItem(boneConfig.UpTo).GetItem(float32(fno)).Position

					motionDirectionVector := motionDirectionToPos.Subed(motionDirectionFromPos).Normalize()
					motionUpVector := motionUpToPos.Subed(motionUpFromPos).Normalize()
					motionCrossVector := motionUpVector.Cross(motionDirectionVector).Normalize()

					motionQuat := mmath.NewMQuaternionFromDirection(motionDirectionVector, motionCrossVector)

					// キャンセルボーン角度
					cancelQuat := mmath.NewMQuaternion()
					for _, cancelBoneName := range boneConfig.Cancels {
						cancelQuat = cancelQuat.Mul(rotMotion.BoneFrames.GetItem(cancelBoneName).Data[float32(fno)].Rotation.GetQuaternion())
					}

					// 調整角度
					invertQuat := mmath.NewMQuaternionFromDegrees(boneConfig.InvertBefore.GetX(), boneConfig.InvertBefore.GetY(), boneConfig.InvertBefore.GetZ())

					quat := cancelQuat.Invert().Mul(motionQuat).Mul(boneQuat.Invert()).Mul(invertQuat).Normalize()

					// ボーンフレーム登録
					bf := deform.NewBoneFrame(float32(fno))
					bf.Registered = true
					bf.Rotation.SetQuaternion(quat)

					rotMotion.AppendBoneFrame(boneConfig.Name, bf)
				}
			}

			err := vmd.Write(rotMotion)
			if err != nil {
				mlog.E("Failed to write rotate vmd: %v", err)
			}

			allRotateMotions = append(allRotateMotions, rotMotion)
		}(i, movMotion)
	}

	wg.Wait()
	bar.Finish()

	return allRotateMotions
}

type boneConfig struct {
	Name          string
	DirectionFrom string
	DirectionTo   string
	UpFrom        string
	UpTo          string
	Cancels       []string
	InvertBefore  *mmath.MVec3
	InvertAfter   *mmath.MVec3
}

var boneConfigs = []*boneConfig{
	{
		Name:          "下半身",
		DirectionFrom: "下半身",
		DirectionTo:   "下半身先",
		UpFrom:        "左足",
		UpTo:          "右足",
		Cancels:       []string{},
		InvertBefore:  &mmath.MVec3{},
		InvertAfter:   &mmath.MVec3{},
	},
	{
		Name:          "上半身",
		DirectionFrom: "上半身",
		DirectionTo:   "上半身2",
		UpFrom:        "左腕",
		UpTo:          "右腕",
		Cancels:       []string{},
		InvertBefore:  &mmath.MVec3{},
		InvertAfter:   &mmath.MVec3{},
	},
	{
		Name:          "上半身2",
		DirectionFrom: "上半身2",
		DirectionTo:   "首",
		UpFrom:        "左腕",
		UpTo:          "右腕",
		Cancels:       []string{"上半身"},
		InvertBefore:  &mmath.MVec3{},
		InvertAfter:   &mmath.MVec3{},
	},
	{
		Name:          "首",
		DirectionFrom: "首",
		DirectionTo:   "頭",
		UpFrom:        "左腕",
		UpTo:          "右腕",
		Cancels:       []string{"上半身", "上半身2"},
		InvertBefore:  &mmath.MVec3{},
		InvertAfter:   &mmath.MVec3{},
	},
	{
		Name:          "頭",
		DirectionFrom: "首",
		DirectionTo:   "頭",
		UpFrom:        "左目",
		UpTo:          "右目",
		Cancels:       []string{"上半身", "上半身2", "首"},
		InvertBefore:  &mmath.MVec3{},
		InvertAfter:   &mmath.MVec3{},
	},
	{
		Name:          "左肩",
		DirectionFrom: "左肩",
		DirectionTo:   "左腕",
		UpFrom:        "上半身2",
		UpTo:          "首",
		Cancels:       []string{"上半身", "上半身2"},
		InvertBefore:  &mmath.MVec3{0, 0, 20},
		InvertAfter:   &mmath.MVec3{},
	},
	{
		Name:          "左腕",
		DirectionFrom: "左腕",
		DirectionTo:   "左ひじ",
		UpFrom:        "上半身2",
		UpTo:          "首",
		Cancels:       []string{"上半身", "上半身2", "左肩"},
		InvertBefore:  &mmath.MVec3{},
		InvertAfter:   &mmath.MVec3{},
	},
	{
		Name:          "左ひじ",
		DirectionFrom: "左ひじ",
		DirectionTo:   "左手首",
		UpFrom:        "上半身2",
		UpTo:          "首",
		Cancels:       []string{"上半身", "上半身2", "左肩", "左腕"},
		InvertBefore:  &mmath.MVec3{},
		InvertAfter:   &mmath.MVec3{},
	},
	{
		Name:          "右肩",
		DirectionFrom: "右肩",
		DirectionTo:   "右腕",
		UpFrom:        "上半身2",
		UpTo:          "首",
		Cancels:       []string{"上半身", "上半身2"},
		InvertBefore:  &mmath.MVec3{0, 0, -20},
		InvertAfter:   &mmath.MVec3{},
	},
	{
		Name:          "右腕",
		DirectionFrom: "右腕",
		DirectionTo:   "右ひじ",
		UpFrom:        "上半身2",
		UpTo:          "首",
		Cancels:       []string{"上半身", "上半身2", "右肩"},
		InvertBefore:  &mmath.MVec3{},
		InvertAfter:   &mmath.MVec3{},
	},
	{
		Name:          "右ひじ",
		DirectionFrom: "右ひじ",
		DirectionTo:   "右手首",
		UpFrom:        "上半身2",
		UpTo:          "首",
		Cancels:       []string{"上半身", "上半身2", "右肩", "右腕"},
		InvertBefore:  &mmath.MVec3{},
		InvertAfter:   &mmath.MVec3{},
	},
	{
		Name:          "左足",
		DirectionFrom: "左足",
		DirectionTo:   "左ひざ",
		UpFrom:        "左足",
		UpTo:          "右足",
		Cancels:       []string{"下半身"},
		InvertBefore:  &mmath.MVec3{},
		InvertAfter:   &mmath.MVec3{},
	},
	{
		Name:          "左ひざ",
		DirectionFrom: "左ひざ",
		DirectionTo:   "左足首",
		UpFrom:        "左足",
		UpTo:          "右足",
		Cancels:       []string{"下半身", "左足"},
		InvertBefore:  &mmath.MVec3{},
		InvertAfter:   &mmath.MVec3{},
	},
	{
		Name:          "左足首",
		DirectionFrom: "左足首",
		DirectionTo:   "左つま先",
		UpFrom:        "左つま先親",
		UpTo:          "左つま先子",
		Cancels:       []string{"下半身", "左足", "左ひざ"},
		InvertBefore:  &mmath.MVec3{},
		InvertAfter:   &mmath.MVec3{},
	},
	{
		Name:          "右足",
		DirectionFrom: "右足",
		DirectionTo:   "右ひざ",
		UpFrom:        "左足",
		UpTo:          "右足",
		Cancels:       []string{"下半身"},
		InvertBefore:  &mmath.MVec3{},
		InvertAfter:   &mmath.MVec3{},
	},
	{
		Name:          "右ひざ",
		DirectionFrom: "右ひざ",
		DirectionTo:   "右足首",
		UpFrom:        "左足",
		UpTo:          "右足",
		Cancels:       []string{"下半身", "右足"},
		InvertBefore:  &mmath.MVec3{},
		InvertAfter:   &mmath.MVec3{},
	},
	{
		Name:          "右足首",
		DirectionFrom: "右足首",
		DirectionTo:   "右つま先",
		UpFrom:        "右つま先親",
		UpTo:          "右つま先子",
		Cancels:       []string{"下半身", "右足", "右ひざ"},
		InvertBefore:  &mmath.MVec3{},
		InvertAfter:   &mmath.MVec3{},
	},
}

package usecase

import (
	"strings"

	"github.com/miu200521358/mlib_go/pkg/mmath"
	"github.com/miu200521358/mlib_go/pkg/mutils/mlog"
	"github.com/miu200521358/mlib_go/pkg/pmx"
	"github.com/miu200521358/mlib_go/pkg/vmd"
	"github.com/miu200521358/mmd-auto-trace-4/pkg/utils"
)

func Rotate(prevMotion *vmd.VmdMotion, modelPath string, motionNum, allNum int) *vmd.VmdMotion {
	mlog.I("[%d/%d] Convert Rotate ...", motionNum, allNum)

	// モデル読み込み
	pr := &pmx.PmxReader{}
	data, err := pr.ReadByFilepath(modelPath)
	if err != nil {
		mlog.E("Failed to read pmx: %v", err)
	}
	pmxModel := data.(*pmx.PmxModel)

	bar := utils.NewProgressBar(len(boneConfigs))

	rotMotion := vmd.NewVmdMotion(strings.Replace(prevMotion.Path, "_move.vmd", "_rotate.vmd", -1))

	for _, fno := range prevMotion.BoneFrames.Get("Camera").RegisteredIndexes.List() {
		{
			bf := vmd.NewBoneFrame(fno)
			bf.Position = prevMotion.BoneFrames.Get("Camera").Get(fno).Position
			rotMotion.AppendRegisteredBoneFrame(pmx.CENTER.String(), bf)
		}
	}

	for _, boneConfig := range boneConfigs {
		bar.Increment()

		if !prevMotion.BoneFrames.Contains(boneConfig.Name) || !prevMotion.BoneFrames.Contains(boneConfig.DirectionFrom) ||
			!prevMotion.BoneFrames.Contains(boneConfig.DirectionTo) || !prevMotion.BoneFrames.Contains(boneConfig.UpFrom) ||
			!prevMotion.BoneFrames.Contains(boneConfig.UpTo) {
			continue
		}

		for _, fno := range prevMotion.BoneFrames.Get(boneConfig.Name).RegisteredIndexes.List() {
			// モデルのボーン角度
			boneDirectionFrom := pmxModel.Bones.GetByName(boneConfig.DirectionFrom).Position
			boneDirectionTo := pmxModel.Bones.GetByName(boneConfig.DirectionTo).Position
			boneUpFrom := pmxModel.Bones.GetByName(boneConfig.UpFrom).Position
			boneUpTo := pmxModel.Bones.GetByName(boneConfig.UpTo).Position

			boneDirectionVector := boneDirectionTo.Subed(boneDirectionFrom).Normalize()
			boneUpVector := boneUpTo.Subed(boneUpFrom).Normalize()
			boneCrossVector := boneUpVector.Cross(boneDirectionVector).Normalize()

			boneQuat := mmath.NewMQuaternionFromDirection(boneDirectionVector, boneCrossVector)

			// モーションのボーン角度
			motionDirectionFromPos := prevMotion.BoneFrames.Get(boneConfig.DirectionFrom).Get(fno).Position
			motionDirectionToPos := prevMotion.BoneFrames.Get(boneConfig.DirectionTo).Get(fno).Position
			motionUpFromPos := prevMotion.BoneFrames.Get(boneConfig.UpFrom).Get(fno).Position
			motionUpToPos := prevMotion.BoneFrames.Get(boneConfig.UpTo).Get(fno).Position

			motionDirectionVector := motionDirectionToPos.Subed(motionDirectionFromPos).Normalize()
			motionUpVector := motionUpToPos.Subed(motionUpFromPos).Normalize()
			motionCrossVector := motionUpVector.Cross(motionDirectionVector).Normalize()

			motionQuat := mmath.NewMQuaternionFromDirection(motionDirectionVector, motionCrossVector)

			// キャンセルボーン角度
			cancelQuat := mmath.NewMQuaternion()
			for _, cancelBoneName := range boneConfig.Cancels {
				cancelQuat.Mul(rotMotion.BoneFrames.Get(cancelBoneName).Get(fno).Rotation)
			}

			// 調整角度
			invertQuat := mmath.NewMQuaternionFromDegrees(boneConfig.Invert.GetX(), boneConfig.Invert.GetY(), boneConfig.Invert.GetZ())

			// ボーンフレーム登録
			bf := vmd.NewBoneFrame(fno)
			bf.Rotation = invertQuat.Mul(cancelQuat.Invert()).Mul(motionQuat).Mul(boneQuat.Invert()).Normalize()

			rotMotion.AppendRegisteredBoneFrame(boneConfig.Name, bf)
		}
	}

	bar.Finish()

	return rotMotion
}

type boneConfig struct {
	Name          string
	DirectionFrom string
	DirectionTo   string
	UpFrom        string
	UpTo          string
	Cancels       []string
	Invert        *mmath.MVec3
}

var boneConfigs = []*boneConfig{
	{
		Name:          "下半身",
		DirectionFrom: "下半身",
		DirectionTo:   "下半身先",
		UpFrom:        "左足",
		UpTo:          "右足",
		Cancels:       []string{},
		Invert:        &mmath.MVec3{},
	},
	{
		Name:          "上半身",
		DirectionFrom: "上半身",
		DirectionTo:   "上半身2",
		UpFrom:        "左腕",
		UpTo:          "右腕",
		Cancels:       []string{},
		Invert:        &mmath.MVec3{},
	},
	{
		Name:          "上半身2",
		DirectionFrom: "上半身2",
		DirectionTo:   "首",
		UpFrom:        "左腕",
		UpTo:          "右腕",
		Cancels:       []string{"上半身"},
		Invert:        &mmath.MVec3{},
	},
	{
		Name:          "首",
		DirectionFrom: "首",
		DirectionTo:   "頭",
		UpFrom:        "左腕",
		UpTo:          "右腕",
		Cancels:       []string{"上半身", "上半身2"},
		Invert:        &mmath.MVec3{},
	},
	{
		Name:          "頭",
		DirectionFrom: "首",
		DirectionTo:   "頭",
		UpFrom:        "左目",
		UpTo:          "右目",
		Cancels:       []string{"上半身", "上半身2", "首"},
		Invert:        &mmath.MVec3{},
	},
	{
		Name:          "左肩",
		DirectionFrom: "左肩",
		DirectionTo:   "左腕",
		UpFrom:        "上半身2",
		UpTo:          "首",
		Cancels:       []string{"上半身", "上半身2"},
		Invert:        &mmath.MVec3{0, 0, 20},
	},
	{
		Name:          "左腕",
		DirectionFrom: "左腕",
		DirectionTo:   "左ひじ",
		UpFrom:        "左腕",
		UpTo:          "右腕",
		Cancels:       []string{"上半身", "上半身2", "左肩"},
		Invert:        &mmath.MVec3{},
	},
	{
		Name:          "左ひじ",
		DirectionFrom: "左ひじ",
		DirectionTo:   "左手首",
		UpFrom:        "左腕",
		UpTo:          "左ひじ",
		Cancels:       []string{"上半身", "上半身2", "左肩", "左腕"},
		Invert:        &mmath.MVec3{},
	},
	{
		Name:          "左手首",
		DirectionFrom: "左手首",
		DirectionTo:   "左人指先",
		UpFrom:        "左親指１",
		UpTo:          "左小指１",
		Cancels:       []string{"上半身", "上半身2", "左肩", "左腕", "左ひじ"},
		Invert:        &mmath.MVec3{},
	},
	{
		Name:          "右肩",
		DirectionFrom: "右肩",
		DirectionTo:   "右腕",
		UpFrom:        "上半身2",
		UpTo:          "首",
		Cancels:       []string{"上半身", "上半身2"},
		Invert:        &mmath.MVec3{0, 0, -20},
	},
	{
		Name:          "右腕",
		DirectionFrom: "右腕",
		DirectionTo:   "右ひじ",
		UpFrom:        "右肩",
		UpTo:          "右腕",
		Cancels:       []string{"上半身", "上半身2", "右肩"},
		Invert:        &mmath.MVec3{},
	},
	{
		Name:          "右ひじ",
		DirectionFrom: "右ひじ",
		DirectionTo:   "右手首",
		UpFrom:        "右腕",
		UpTo:          "右ひじ",
		Cancels:       []string{"上半身", "上半身2", "右肩", "右腕"},
		Invert:        &mmath.MVec3{},
	},
	{
		Name:          "右手首",
		DirectionFrom: "右手首",
		DirectionTo:   "右人指先",
		UpFrom:        "右親指１",
		UpTo:          "右小指１",
		Cancels:       []string{"上半身", "上半身2", "右肩", "右腕", "右ひじ"},
		Invert:        &mmath.MVec3{},
	},
	{
		Name:          "左足",
		DirectionFrom: "左足",
		DirectionTo:   "左ひざ",
		UpFrom:        "左足",
		UpTo:          "右足",
		Cancels:       []string{"下半身"},
		Invert:        &mmath.MVec3{},
	},
	{
		Name:          "左ひざ",
		DirectionFrom: "左ひざ",
		DirectionTo:   "左足首",
		UpFrom:        "左足",
		UpTo:          "右足",
		Cancels:       []string{"下半身", "左足"},
		Invert:        &mmath.MVec3{},
	},
	{
		Name:          "左足首",
		DirectionFrom: "左足首",
		DirectionTo:   "左つま先",
		UpFrom:        "左つま先親",
		UpTo:          "左つま先子",
		Cancels:       []string{"下半身", "左足", "左ひざ"},
		Invert:        &mmath.MVec3{},
	},
	{
		Name:          "右足",
		DirectionFrom: "右足",
		DirectionTo:   "右ひざ",
		UpFrom:        "左足",
		UpTo:          "右足",
		Cancels:       []string{"下半身"},
		Invert:        &mmath.MVec3{},
	},
	{
		Name:          "右ひざ",
		DirectionFrom: "右ひざ",
		DirectionTo:   "右足首",
		UpFrom:        "左足",
		UpTo:          "右足",
		Cancels:       []string{"下半身", "右足"},
		Invert:        &mmath.MVec3{},
	},
	{
		Name:          "右足首",
		DirectionFrom: "右足首",
		DirectionTo:   "右つま先",
		UpFrom:        "右つま先親",
		UpTo:          "右つま先子",
		Cancels:       []string{"下半身", "右足", "右ひざ"},
		Invert:        &mmath.MVec3{},
	},
}

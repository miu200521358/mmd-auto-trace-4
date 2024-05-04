package usecase

import (
	"fmt"
	"strings"
	"sync"

	"github.com/cheggaaa/pb/v3"
	"github.com/miu200521358/mlib_go/pkg/mutils/mlog"
	"github.com/miu200521358/mlib_go/pkg/vmd"
	"github.com/miu200521358/mmd-auto-trace-4/pkg/model"
)

func IntegrateWrist(allFrames []*model.Frames, all4dRotateMotions []*vmd.VmdMotion, allMpRotateMotions []*vmd.VmdMotion) []*vmd.VmdMotion {
	allRotateMotions := make([]*vmd.VmdMotion, len(all4dRotateMotions))

	// 全体のタスク数をカウント
	totalFrames := len(all4dRotateMotions)
	for _, rotMotion := range all4dRotateMotions {
		totalFrames += int(rotMotion.GetMaxFrame()) * 2
	}

	bar := pb.StartNew(totalFrames)
	var wg sync.WaitGroup

	for i := range allFrames {
		wg.Add(1)

		go func(i int, frames *model.Frames, dRotMotion *vmd.VmdMotion, mpRotMotion *vmd.VmdMotion) {
			defer wg.Done()
			rotMotion := integrateWristMotion(frames, dRotMotion, mpRotMotion, bar)

			if mlog.IsDebug() {
				rotMotion.Path = strings.Replace(all4dRotateMotions[i].Path, "_rot.vmd", "_wrist.vmd", -1)
				err := vmd.Write(rotMotion)
				if err != nil {
					mlog.E("Failed to write leg ik vmd: %v", err)
				}
			}

			allRotateMotions[i] = rotMotion
		}(i, allFrames[i], all4dRotateMotions[i], allMpRotateMotions[i])
	}

	wg.Wait()
	bar.Finish()

	return allRotateMotions
}

func integrateWristMotion(frames *model.Frames, dRotateMotion *vmd.VmdMotion, mpRotateMotion *vmd.VmdMotion, bar *pb.ProgressBar) *vmd.VmdMotion {
	for _, direction := range []string{"左", "右"} {
		wristName := fmt.Sprintf("%s手首", direction)
		var mpWristName string
		switch direction {
		case "左":
			mpWristName = "left wrist"
		case "右":
			mpWristName = "right wrist"
		}
		for _, fno := range mpRotateMotion.BoneFrames.GetItem(wristName).RegisteredIndexes {
			bar.Increment()
			visibility := frames.Frames[int(fno)].Mediapipe[mpWristName].Visibility

			if visibility > 0.99 {
				wristBf := mpRotateMotion.BoneFrames.GetItem(wristName).GetItem(fno)
				dRotateMotion.AppendRegisteredBoneFrame(wristName, wristBf)
			}
		}
	}
	return dRotateMotion
}

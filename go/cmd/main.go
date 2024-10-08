package main

import (
	"flag"
	"os"
	"path/filepath"
	"time"

	"github.com/miu200521358/mlib_go/pkg/mutils/mlog"
	"github.com/miu200521358/mmd-auto-trace-4/pkg/usecase"
	"github.com/miu200521358/mmd-auto-trace-4/pkg/utils"
)

var logLevel string
var modelPath string
var dirPath string
var limitMinutes int

func init() {
	flag.StringVar(&logLevel, "logLevel", "INFO", "set log level")
	flag.StringVar(&modelPath, "modelPath", "", "set model path")
	flag.StringVar(&dirPath, "dirPath", "", "set directory path")
	flag.IntVar(&limitMinutes, "limitMinutes", 30, "set directory path")
	flag.Parse()

	switch logLevel {
	case "INFO":
		mlog.SetLevel(mlog.INFO)
	default:
		mlog.SetLevel(mlog.DEBUG)
	}
}

func main() {
	if modelPath == "" || dirPath == "" {
		mlog.E("modelPath and dirPath must be provided")
		os.Exit(1)
	}

	mlog.I("Unpack json ================")
	allFrames, err := usecase.Unpack(dirPath)
	if err != nil {
		mlog.E("Failed to unpack: %v", err)
		return
	}

	startTime := time.Now()

	allNum := len(allFrames)
	for i, frames := range allFrames {
		motionNum := i + 1

		if _, err := os.Stat(filepath.Join(filepath.Dir(frames.Path), utils.GetCompleteName(frames.Path))); err == nil {
			mlog.I("[%d/%d] Finished Convert Motion ===========================", motionNum, allNum)
			continue
		}

		mlog.I("[%d/%d] Convert Motion ===========================", motionNum, allNum)

		moveMotion := usecase.Move(frames, motionNum, allNum)

		if mlog.IsDebug() {
			utils.WriteVmdMotions(frames, moveMotion, dirPath, "1_move", "Move", motionNum, allNum)
		}

		rotateMotion := usecase.Rotate(moveMotion, modelPath, motionNum, allNum)

		if mlog.IsDebug() {
			utils.WriteVmdMotions(frames, rotateMotion, dirPath, "2_rotate", "Rotate", motionNum, allNum)
		}

		legIkMotion := usecase.ConvertLegIk(rotateMotion, modelPath, motionNum, allNum)

		if mlog.IsDebug() {
			utils.WriteVmdMotions(frames, legIkMotion, dirPath, "3_legIk", "LegIK", motionNum, allNum)
		}

		groundMotion := usecase.FixGround(legIkMotion, modelPath, motionNum, allNum)

		if mlog.IsDebug() {
			utils.WriteVmdMotions(frames, groundMotion, dirPath, "4_ground", "Ground", motionNum, allNum)
		}

		heelMotion := usecase.FixHeel(frames, groundMotion, modelPath, motionNum, allNum)

		if mlog.IsDebug() {
			utils.WriteVmdMotions(frames, heelMotion, dirPath, "5_heel", "Heel", motionNum, allNum)
		}

		armIkMotion := usecase.ConvertArmIk(heelMotion, modelPath, motionNum, allNum)

		utils.WriteVmdMotions(frames, armIkMotion, dirPath, "full", "Full", motionNum, allNum)

		narrowReduceMotion := usecase.Reduce(armIkMotion, modelPath, 0.05, 0.00001, 0, "narrow", motionNum, allNum)

		utils.WriteVmdMotions(frames, narrowReduceMotion, dirPath, "reduce_narrow", "Narrow Reduce", motionNum, allNum)

		wideReduceMotions := usecase.Reduce(armIkMotion, modelPath, 0.07, 0.00005, 2, "wide", motionNum, allNum)

		utils.WriteVmdMotions(frames, wideReduceMotions, dirPath, "reduce_wide", "Wide Reduce", motionNum, allNum)

		utils.WriteComplete(dirPath, frames.Path)

		// 開始時間から指定時間過ぎてたら終了
		if time.Since(startTime) > time.Duration(limitMinutes)*time.Minute {
			return
		}
	}

	// complete ファイルを出力する
	{
		completePath := filepath.Join(dirPath, "all_complete")
		mlog.I("Output Complete File %s", completePath)
		f, err := os.Create(completePath)
		if err != nil {
			mlog.E("Failed to create complete file: %v", err)
			return
		}
		defer f.Close()
	}

	mlog.I("Done!")
}

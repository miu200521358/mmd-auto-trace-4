package main

import (
	"os"

	"github.com/miu200521358/mlib_go/pkg/mutils/mlog"
	"github.com/miu200521358/mlib_go/pkg/vmd"

	"github.com/miu200521358/mmd-auto-trace-4/pkg/usecase"
)

func init() {
	mlog.SetLevel(mlog.DEBUG)
}

func main() {
	dir_path := os.Args[1]
	mlog.I("dir_path: %v", dir_path)

	mlog.I("Unpack json ...")
	allFrames, err := usecase.Unpack(dir_path)
	if err != nil {
		mlog.E("Failed to unpack: %v", err)
		return
	}

	mlog.I("Move Motion ...")
	allMoveMotions := usecase.Move(allFrames)
	for i, motion := range allMoveMotions {
		mlog.I("motion[%v]: %v", i, motion.GetPath())
		vmd.Write(motion)
	}
}

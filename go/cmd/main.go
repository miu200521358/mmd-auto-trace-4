package main

import (
	"os"
	"strings"

	"github.com/miu200521358/mlib_go/pkg/mutils/mlog"

	"github.com/miu200521358/mmd-auto-trace-4/pkg/usecase"
)

func init() {
	mlog.SetLevel(mlog.DEBUG)
}

func main() {
	commands := strings.Split(os.Args[1], ",")
	mlog.I("commands: %v", commands)

	json_path := os.Args[2]
	mlog.I("json_path: %v", json_path)

	frames, err := usecase.Unpack(json_path)
	if err != nil {
		mlog.E("Failed to unpack: %v", err)
		return
	}

	for i, frame := range frames.Frames {
		mlog.I("frame[%v]: %v", i, frame)
	}
}

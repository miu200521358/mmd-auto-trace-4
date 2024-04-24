package main

import (
	"os"
	"strings"

	"github.com/miu200521358/mlib_go/pkg/mutils/mlog"

)

func init() {
	mlog.SetLevel(mlog.DEBUG)
}

func main() {
	commands := strings.Split(os.Args[1], ",")

	mlog.I("commands: %v", commands)

}

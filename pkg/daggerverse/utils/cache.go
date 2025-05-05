// Skycaptain: Daggerverse
//
// SPDX-License-Identifier: BSD-3-Clause
package utils

import (
	"fmt"

	"dagger.io/dagger"
	"github.com/google/uuid"
)

// BustDaggerCache is a with-function that busts the Dagger cache by adding a random but unique
// environment variable to the container.
func BustDaggerCache() func(*dagger.Container) *dagger.Container {
	return func(ctr *dagger.Container) *dagger.Container {
		return ctr.WithEnvVariable(fmt.Sprintf("_DAGGERVERSE_BUST_CACHE_%s", uuid.New().String()), "")
	}
}

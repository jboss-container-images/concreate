// Copyright 2021 Red Hat, Inc. and/or its affiliates
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package main

import (
	"flag"
	"github.com/kiegroup/kogito-operator/core/client"
	"github.com/kiegroup/kogito-operator/core/logger"
	"github.com/kiegroup/rhpam-kogito-operator/controllers"
	"github.com/kiegroup/rhpam-kogito-operator/meta"
	"k8s.io/apimachinery/pkg/runtime"
	"os"
	"strings"

	_ "k8s.io/client-go/plugin/pkg/client/auth/gcp"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/log/zap"
	// +kubebuilder:scaffold:imports
)

var (
	scheme   *runtime.Scheme
	setupLog = logger.GetLogger("setup")
)

func init() {
	scheme = meta.GetRegisteredSchema()
}

func main() {
	var metricsAddr string
	var enableLeaderElection bool
	flag.StringVar(&metricsAddr, "metrics-addr", ":8080", "The address the metric endpoint binds to.")
	flag.BoolVar(&enableLeaderElection, "enable-leader-election", false,
		"Enable leader election for controller manager. "+
			"Enabling this will ensure there is only one active controller manager.")
	flag.Parse()

	ctrl.SetLogger(zap.New(zap.UseDevMode(isDebugMode())))
	watchNamespace := getWatchNamespace()
	mgr, err := ctrl.NewManager(ctrl.GetConfigOrDie(), ctrl.Options{
		Scheme:             scheme,
		MetricsBindAddress: metricsAddr,
		Port:               9443,
		LeaderElection:     enableLeaderElection,
		LeaderElectionID:   "4662f1d5.kiegroup.org",
		Namespace:          watchNamespace,
	})
	if err != nil {
		setupLog.Error(err, "unable to start manager")
		os.Exit(1)
	}

	kubeCli := client.NewForController(mgr)

	if err = (&controllers.KogitoRuntimeReconciler{
		Client: kubeCli,
		Log:    logger.GetLogger("kogitoruntime_controllers"),
		Scheme: mgr.GetScheme(),
	}).SetupWithManager(mgr); err != nil {
		setupLog.Error(err, "unable to create controller", "controller", "KogitoRuntime")
		os.Exit(1)
	}
	if err = (&controllers.KogitoBuildReconciler{
		Client: kubeCli,
		Log:    logger.GetLogger("kogitoBuild-controller"),
		Scheme: mgr.GetScheme(),
	}).SetupWithManager(mgr); err != nil {
		setupLog.Error(err, "unable to create controller", "controller", "KogitoBuild")
		os.Exit(1)
	}
	// +kubebuilder:scaffold:builder

	setupLog.Info("starting manager")
	if err := mgr.Start(ctrl.SetupSignalHandler()); err != nil {
		setupLog.Error(err, "problem running manager")
		os.Exit(1)
	}
}

// getWatchNamespace returns the Namespace the operator should be watching for changes
func getWatchNamespace() string {
	// WatchNamespaceEnvVar is the constant for env variable WATCH_NAMESPACE
	// which specifies the Namespace to watch.
	// An empty value means the operator is running with cluster scope.
	var watchNamespaceEnvVar = "WATCH_NAMESPACE"

	ns, _ := os.LookupEnv(watchNamespaceEnvVar)

	// Check if operator is running as cluster scoped
	if len(ns) == 0 {
		setupLog.Info(
			"The operator is running as cluster scoped. It will watch and manage resources in all namespaces",
			"Env Var lookup", watchNamespaceEnvVar)
	}
	return ns
}

func isDebugMode() bool {
	var debug = "DEBUG"
	devMode, _ := os.LookupEnv(debug)

	if strings.ToUpper(devMode) == "TRUE" {
		setupLog.Info("Running in Debug Mode")
		return true
	}
	return false

}

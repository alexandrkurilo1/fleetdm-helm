CLUSTER_NAME ?= fleet
NAMESPACE    ?= fleet
RELEASE      ?= fleet
CHART        ?= charts/fleet
KIND_IMAGE   ?= kindest/node:v1.31.4
FLEET_URL    ?= https://localhost:8443
# LAN address added to the TLS certificate so agents on other machines can enroll.
HOST_IP      ?= $(shell ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $$1}')
HELM_ARGS    ?=
comma := ,

.DEFAULT_GOAL := help
.PHONY: help check-tools cluster cluster-delete install uninstall verify test ca lint template

help: ## Show available targets
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

check-tools:
	@for t in docker kind kubectl helm; do command -v $$t >/dev/null || { echo "missing: $$t"; exit 1; }; done

cluster: check-tools ## Create the local kind cluster
	@if kind get clusters | grep -qx '$(CLUSTER_NAME)'; then \
		echo "kind cluster '$(CLUSTER_NAME)' already exists"; \
	else \
		kind create cluster --name $(CLUSTER_NAME) --image $(KIND_IMAGE) --config hack/kind-config.yaml --wait 120s; \
	fi
	kubectl cluster-info --context kind-$(CLUSTER_NAME)

install: check-tools ## Install/upgrade the Helm chart (runs `fleet prepare db` automatically)
	helm upgrade --install $(RELEASE) $(CHART) \
		--namespace $(NAMESPACE) --create-namespace \
		--kube-context kind-$(CLUSTER_NAME) \
		$(if $(HOST_IP),--set 'fleet.tls.ipAddresses={127.0.0.1$(comma)$(HOST_IP)}') \
		--wait --wait-for-jobs --timeout 10m $(HELM_ARGS)
	@printf "\nFleet UI: %s  (export CA: make ca)\n" "$(FLEET_URL)"

uninstall: ## Remove the release, its PVCs and the namespace
	-helm uninstall $(RELEASE) --namespace $(NAMESPACE) --kube-context kind-$(CLUSTER_NAME) --wait
	-kubectl --context kind-$(CLUSTER_NAME) -n $(NAMESPACE) delete pvc -l app.kubernetes.io/instance=$(RELEASE) --wait
	-kubectl --context kind-$(CLUSTER_NAME) delete namespace $(NAMESPACE) --wait

cluster-delete: ## Delete the kind cluster entirely
	kind delete cluster --name $(CLUSTER_NAME)

verify: ## Check that Fleet, MySQL and Redis are operational
	KUBE_CONTEXT=kind-$(CLUSTER_NAME) NAMESPACE=$(NAMESPACE) RELEASE=$(RELEASE) FLEET_URL=$(FLEET_URL) ./hack/verify.sh

test: ## Run `helm test` (in-cluster /healthz probe)
	helm test $(RELEASE) --namespace $(NAMESPACE) --kube-context kind-$(CLUSTER_NAME) --logs

ca: ## Export the self-signed CA to ./fleet-ca.crt (for browsers and agents)
	kubectl --context kind-$(CLUSTER_NAME) -n $(NAMESPACE) get secret $(RELEASE)-tls -o jsonpath='{.data.ca\.crt}' | base64 -d > fleet-ca.crt
	@echo "wrote fleet-ca.crt"

lint: ## Lint and render the chart
	helm lint $(CHART) --strict
	helm template $(RELEASE) $(CHART) --namespace $(NAMESPACE) > /dev/null

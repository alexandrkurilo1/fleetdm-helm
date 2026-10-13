{{- define "fleet.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "fleet.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{- define "fleet.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
app.kubernetes.io/name: {{ include "fleet.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/* Selector labels; call with (dict "ctx" $ "component" "server") */}}
{{- define "fleet.selectorLabels" -}}
app.kubernetes.io/name: {{ include "fleet.name" .ctx }}
app.kubernetes.io/instance: {{ .ctx.Release.Name }}
app.kubernetes.io/component: {{ .component }}
{{- end }}

{{- define "fleet.image" -}}
{{- printf "%s:%s" .Values.fleet.image.repository (default .Chart.AppVersion .Values.fleet.image.tag) }}
{{- end }}

{{- define "fleet.mysql.fullname" -}}
{{- printf "%s-mysql" (include "fleet.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "fleet.redis.fullname" -}}
{{- printf "%s-redis" (include "fleet.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "fleet.mysql.secretName" -}}
{{- if .Values.mysql.enabled }}
{{- default (include "fleet.mysql.fullname" .) .Values.mysql.auth.existingSecret }}
{{- else }}
{{- required "externalMysql.existingSecret is required when mysql.enabled=false" .Values.externalMysql.existingSecret }}
{{- end }}
{{- end }}

{{- define "fleet.mysql.address" -}}
{{- if .Values.mysql.enabled }}
{{- printf "%s:3306" (include "fleet.mysql.fullname" .) }}
{{- else }}
{{- required "externalMysql.address is required when mysql.enabled=false" .Values.externalMysql.address }}
{{- end }}
{{- end }}

{{- define "fleet.mysql.database" -}}
{{- ternary .Values.mysql.auth.database .Values.externalMysql.database .Values.mysql.enabled }}
{{- end }}

{{- define "fleet.mysql.username" -}}
{{- ternary .Values.mysql.auth.username .Values.externalMysql.username .Values.mysql.enabled }}
{{- end }}

{{- define "fleet.redis.address" -}}
{{- if .Values.redis.enabled }}
{{- printf "%s:6379" (include "fleet.redis.fullname" .) }}
{{- else }}
{{- required "externalRedis.address is required when redis.enabled=false" .Values.externalRedis.address }}
{{- end }}
{{- end }}

{{- define "fleet.tls.secretName" -}}
{{- default (printf "%s-tls" (include "fleet.fullname" .)) .Values.fleet.tls.existingSecret }}
{{- end }}

{{/*
Environment shared by the Fleet server and the migration Job.
*/}}
{{- define "fleet.env" -}}
- name: FLEET_MYSQL_ADDRESS
  value: {{ include "fleet.mysql.address" . | quote }}
- name: FLEET_MYSQL_DATABASE
  value: {{ include "fleet.mysql.database" . | quote }}
- name: FLEET_MYSQL_USERNAME
  value: {{ include "fleet.mysql.username" . | quote }}
- name: FLEET_MYSQL_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ include "fleet.mysql.secretName" . }}
      key: mysql-password
- name: FLEET_REDIS_ADDRESS
  value: {{ include "fleet.redis.address" . | quote }}
- name: FLEET_SERVER_PRIVATE_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "fleet.fullname" . }}
      key: server-private-key
- name: FLEET_LOGGING_JSON
  value: {{ .Values.fleet.logging.json | quote }}
- name: FLEET_LOGGING_DEBUG
  value: {{ .Values.fleet.logging.debug | quote }}
{{- with .Values.fleet.extraEnv }}
{{ toYaml . }}
{{- end }}
{{- end }}

{{/* Init container that blocks until MySQL accepts authenticated connections. */}}
{{- define "fleet.waitForMysql" -}}
- name: wait-for-mysql
  image: "{{ .Values.mysql.image.repository }}:{{ .Values.mysql.image.tag }}"
  imagePullPolicy: {{ .Values.mysql.image.pullPolicy }}
  command:
    - sh
    - -c
    - |
      host="${FLEET_MYSQL_ADDRESS%:*}"; port="${FLEET_MYSQL_ADDRESS##*:}"
      until mysqladmin ping -h "$host" -P "$port" -u "$FLEET_MYSQL_USERNAME" -p"$FLEET_MYSQL_PASSWORD" --silent; do
        echo "waiting for MySQL at $host:$port"; sleep 3
      done
  env:
    - name: FLEET_MYSQL_ADDRESS
      value: {{ include "fleet.mysql.address" . | quote }}
    - name: FLEET_MYSQL_USERNAME
      value: {{ include "fleet.mysql.username" . | quote }}
    - name: FLEET_MYSQL_PASSWORD
      valueFrom:
        secretKeyRef:
          name: {{ include "fleet.mysql.secretName" . }}
          key: mysql-password
  resources:
    requests:
      cpu: 10m
      memory: 32Mi
{{- end }}

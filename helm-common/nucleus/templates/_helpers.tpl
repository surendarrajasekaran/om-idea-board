{{/*
Expand the name of the chart.
*/}}
{{- define "nucleus.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "nucleus.fullname" -}}
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

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "nucleus.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "nucleus.labels" -}}
helm.sh/chart: {{ include "nucleus.chart" . }}
{{ include "nucleus.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- with (mergeOverwrite (deepCopy .Values.global.additionalLabels) .Values.commonLabels) }}
{{ toYaml . }}
{{- end }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "nucleus.selectorLabels" -}}
app.kubernetes.io/name: {{ include "nucleus.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "nucleus.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "nucleus.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create the name of the service to use
*/}}
{{- define "nucleus.serviceName" -}}
{{- default (include "nucleus.fullname" .) .Values.service.name }}
{{- end }}


{{/*
Common annotations
*/}}
{{- define "nucleus.annotations" -}}
app.kubernetes.io/chart: nucleus
{{- with (mergeOverwrite (deepCopy .Values.global.additionalAnnotations) .Values.commonAnnotations) }}
{{ toYaml . }}
{{- end }}
{{- end -}}

{{/*
Format annotations with support for multi-line values
Preserves multi-line strings using YAML literal block scalar syntax (|)
*/}}
{{- define "nucleus.formatAnnotations" -}}
{{- range $key, $value := . }}
{{- $strValue := toString $value }}
{{- if contains "\n" $strValue }}
{{ $key }}: |
{{ $strValue | indent 2 }}
{{- else }}
{{ $key }}: {{ $value | quote }}
{{- end }}
{{- end }}
{{- end -}}

{{/*
Combined environment variables from global.env, additionalContainerEnv, and env
Uses map to merge and deduplicate, with precedence: global.env < additionalContainerEnv < env
Returns YAML format environment variables ready for container env section
*/}}
{{- define "nucleus.combinedEnv" -}}
{{- $envMap := dict }}
{{- $values := .Values | default dict }}
{{- if and (hasKey $values "global") (hasKey $values.global "env") }}
{{- range $key, $value := $values.global.env }}
{{- $_ := set $envMap $key $value }}
{{- end }}
{{- end }}
{{- if hasKey $values "additionalContainerEnv" }}
{{- range $key, $value := $values.additionalContainerEnv }}
{{- $_ := set $envMap $key $value }}
{{- end }}
{{- end }}
{{- if hasKey $values "env" }}
{{- range $key, $value := $values.env }}
{{- $_ := set $envMap $key $value }}
{{- end }}
{{- end }}
{{- range $key, $value := $envMap }}
- name: {{ $key }}
  value: {{ $value | quote }}
{{- end }}
{{- end -}}


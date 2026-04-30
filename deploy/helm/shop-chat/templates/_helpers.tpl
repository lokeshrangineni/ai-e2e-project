{{/*
Expand the name of the chart.
*/}}
{{- define "shop-chat.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "shop-chat.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- printf "%s" $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{/*
Backend component full name.
*/}}
{{- define "shop-chat.backend.fullname" -}}
{{- printf "%s-backend" (include "shop-chat.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
UI component full name.
*/}}
{{- define "shop-chat.ui.fullname" -}}
{{- printf "%s-ui" (include "shop-chat.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Chart label.
*/}}
{{- define "shop-chat.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels applied to all resources.
*/}}
{{- define "shop-chat.labels" -}}
helm.sh/chart: {{ include "shop-chat.chart" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- with .Values.commonLabels }}
{{ toYaml . }}
{{- end }}
{{- end }}

{{/*
Selector labels for the backend.
*/}}
{{- define "shop-chat.backend.selectorLabels" -}}
app.kubernetes.io/name: {{ include "shop-chat.name" . }}-backend
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Selector labels for the UI.
*/}}
{{- define "shop-chat.ui.selectorLabels" -}}
app.kubernetes.io/name: {{ include "shop-chat.name" . }}-ui
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

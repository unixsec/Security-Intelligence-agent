{{/*
Common labels
*/}}
{{- define "sia.labels" -}}
app.kubernetes.io/name: sia
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end }}

{{/*
Image reference helper
*/}}
{{- define "sia.image" -}}
{{- $registry := .global.imageRegistry -}}
{{- $repo := .image.repository -}}
{{- $tag := .image.tag | default .chartVersion -}}
{{- if $registry -}}
{{ $registry }}/{{ $repo }}:{{ $tag }}
{{- else -}}
{{ $repo }}:{{ $tag }}
{{- end -}}
{{- end }}

{{/*
Pod imagePullSecrets
*/}}
{{- define "sia.imagePullSecrets" -}}
{{- if .Values.global.imagePullSecrets }}
imagePullSecrets:
  {{- range .Values.global.imagePullSecrets }}
  - name: {{ . }}
  {{- end }}
{{- end }}
{{- end }}

{{/*
Pod-level securityContext for Python workloads (non-root UID 1000).
*/}}
{{- define "sia.podSecurityContext" -}}
runAsNonRoot: true
runAsUser: 1000
runAsGroup: 1000
fsGroup: 1000
seccompProfile:
  type: RuntimeDefault
{{- end }}

{{/*
Container-level securityContext (hardened).
SEC-009 — readOnlyRootFilesystem, drop ALL caps, no priv escalation.
*/}}
{{- define "sia.containerSecurityContext" -}}
readOnlyRootFilesystem: true
allowPrivilegeEscalation: false
privileged: false
capabilities:
  drop:
    - ALL
{{- end }}

{{/*
Writable emptyDir volumes required when readOnlyRootFilesystem is true.
Includes caches for huggingface / sentence-transformers / fontconfig (weasyprint).
*/}}
{{- define "sia.writableVolumes" -}}
- name: tmp
  emptyDir:
    sizeLimit: 256Mi
- name: cache
  emptyDir:
    sizeLimit: 2Gi
- name: run
  emptyDir:
    sizeLimit: 16Mi
{{- end }}

{{- define "sia.writableVolumeMounts" -}}
- name: tmp
  mountPath: /tmp
- name: cache
  mountPath: /home/sia/.cache
- name: run
  mountPath: /var/run
{{- end }}

{{/*
Secrets mounted as files (SEC-008).
The application reads SECRETS_DIR=/etc/sia/secrets first, env second.
*/}}
{{- define "sia.secretsVolume" -}}
- name: sia-secrets
  secret:
    secretName: sia-secrets
    defaultMode: 0400
{{- end }}

{{- define "sia.secretsVolumeMount" -}}
- name: sia-secrets
  mountPath: /etc/sia/secrets
  readOnly: true
{{- end }}

{{/*
TLS CA volumes (SEC-007). Optional; only created if caSecretName is set.
*/}}
{{- define "sia.tlsVolumes" -}}
{{- if .Values.mysql.tls.caSecretName }}
- name: mysql-ca
  secret:
    secretName: {{ .Values.mysql.tls.caSecretName }}
    defaultMode: 0444
{{- end }}
{{- if and .Values.redis.tls.enabled .Values.redis.tls.caSecretName }}
- name: redis-ca
  secret:
    secretName: {{ .Values.redis.tls.caSecretName }}
    defaultMode: 0444
{{- end }}
{{- end }}

{{- define "sia.tlsVolumeMounts" -}}
{{- if .Values.mysql.tls.caSecretName }}
- name: mysql-ca
  mountPath: /etc/sia/tls/mysql
  readOnly: true
{{- end }}
{{- if and .Values.redis.tls.enabled .Values.redis.tls.caSecretName }}
- name: redis-ca
  mountPath: /etc/sia/tls/redis
  readOnly: true
{{- end }}
{{- end }}

{{/*
Topology spread for HA (SEC-019).
*/}}
{{- define "sia.topologySpread" -}}
topologySpreadConstraints:
  - maxSkew: 1
    topologyKey: kubernetes.io/hostname
    whenUnsatisfiable: ScheduleAnyway
    labelSelector:
      matchLabels:
        app.kubernetes.io/name: sia
        app.kubernetes.io/component: {{ .component }}
  - maxSkew: 1
    topologyKey: topology.kubernetes.io/zone
    whenUnsatisfiable: ScheduleAnyway
    labelSelector:
      matchLabels:
        app.kubernetes.io/name: sia
        app.kubernetes.io/component: {{ .component }}
{{- end }}

{{/*
Env vars shared by backend workloads.
Combines ConfigMap envFrom plus key cache-dir overrides needed when
readOnlyRootFilesystem=true and HOME=/home/sia.
*/}}
{{- define "sia.backendEnv" -}}
- name: HOME
  value: /home/sia
- name: HF_HOME
  value: /home/sia/.cache/huggingface
- name: TRANSFORMERS_CACHE
  value: /home/sia/.cache/huggingface
- name: FONTCONFIG_PATH
  value: /home/sia/.cache/fontconfig
- name: SIA_SECRETS_DIR
  value: /etc/sia/secrets
{{- end }}

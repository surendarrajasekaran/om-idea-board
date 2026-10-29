# Nucleus Helm Chart

A flexible, reusable Helm chart designed to abstract common Kubernetes resource creation patterns. This chart serves as a foundation for deploying various types of applications with standardized configurations.

## Features

- **Flexible Workloads**: Support for Deployments and StatefulSets
- **Auto-scaling**: Built-in support for HPA and KEDA
- **External Secrets**: Integration with AWS Secrets Manager via External Secrets Operator
- **Service Management**: Configurable service creation with multiple port support
- **Security**: Comprehensive security context and RBAC configuration
- **Observability**: Health check probes and pod disruption budgets
- **Extensibility**: Support for init containers, sidecars, ConfigMaps, Secrets, CronJobs, and additional Kubernetes resources

## Breaking Changes

### Version 0.2.0+

- **Removed**: `global.additionalConfigMaps` - Global ConfigMaps are no longer supported. Use chart-specific `additionalConfigMaps` instead.
- **Removed**: `global.externalSecrets` - Global external secrets array is no longer supported. Use chart-specific `externalSecrets` configuration.
- **Changed**: External secrets template structure simplified. The secret name can now be customized via `externalSecrets.name`.
- **Added**: `externalSecrets.annotations` for custom external secret annotations.

## Prerequisites

- Kubernetes 1.19+
- Helm 3.0+
- External Secrets Operator (if using external secrets)
- KEDA (if using KEDA autoscaling)

## Installation

### Add the Helm Repository

```bash
# Add the GitHub Pages hosted repository
helm repo add nucleus https://flawlessbyte.github.io/nucleus
helm repo update
```

### Basic Installation

```bash
helm install my-app nucleus/nucleus
```

### Installation with Custom Values

```bash
helm install my-app nucleus/nucleus -f my-values.yaml
```

### Local Development

#### Prerequisites for Local Development

```bash
# Install Helm
brew install helm

# Verify installation
helm version
```

#### Local Testing and Packaging

```bash
# Lint the chart
helm lint .

# Test template rendering
helm template test-release . --values values.yaml

# Package the chart
helm package . --destination ./charts/

# Test installation (dry-run)
helm install test-release ./charts/nucleus-1.0.0.tgz --dry-run
```

## Configuration

### Basic Application Deployment

Here's a minimal example for deploying a web application:

```yaml
# my-values.yaml
image:
  repository: nginx
  tag: "1.21"
  pullPolicy: IfNotPresent

containerPorts:
  - name: http
    containerPort: 80
    protocol: TCP

service:
  enabled: true
  type: ClusterIP
  ports:
    - name: http
      port: 80
      targetPort: 80
      protocol: TCP

resources:
  limits:
    cpu: 500m
    memory: 512Mi
  requests:
    cpu: 250m
    memory: 256Mi

livenessProbe:
  httpGet:
    path: /
    port: 80
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /
    port: 80
  initialDelaySeconds: 5
  periodSeconds: 5
```

### StatefulSet Configuration

For applications requiring persistent storage:

```yaml
workload:
  kind: StatefulSet
  replicaCount: 3

volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: ["ReadWriteOnce"]
      storageClassName: "fast-ssd"
      resources:
        requests:
          storage: 10Gi

volumeMounts:
  - name: data
    mountPath: /data
```

### Auto-scaling Configuration

#### HPA (Horizontal Pod Autoscaler)

```yaml
autoscaling:
  enabled: true
  type: hpa
  minReplicas: 2
  maxReplicas: 10
  hpa:
    targetCPUUtilizationPercentage: 70
    targetMemoryUtilizationPercentage: 80
    metrics:
      - type: Resource
        resource:
          name: cpu
          target:
            type: Utilization
            averageUtilization: 70
```

#### KEDA

```yaml
autoscaling:
  enabled: true
  type: keda
  minReplicas: 1
  maxReplicas: 50
  keda:
    triggers:
      - type: prometheus
        metadata:
          serverAddress: http://prometheus-server.monitoring.svc.cluster.local
          metricName: http_requests_per_second
          query: sum(rate(http_requests_total[1m]))
          threshold: "100"
```

### External Secrets Integration

```yaml
externalSecrets:
  enabled: true
  name: my-app-secrets  # Optional: custom secret name
  annotations:          # Optional: custom annotations
    flawlessbyte.dev/secret-type: application
  secretStoreRef:
    name: aws-secrets-manager-store
    kind: ClusterSecretStore
  dataFrom:
    - extract:
        key: myapp/production/secrets
        version: AWSCURRENT

envFrom:
  - secretRef:
      name: my-app-secrets  # Use the custom name or default fullname
```

### Init Containers and Sidecars

```yaml
initContainers:
  - name: migration
    image: myapp/migrations:latest
    command: ["python", "manage.py", "migrate"]
    envFrom:
      - secretRef:
          name: database-secret

extraContainers:
  - name: log-shipper
    image: fluent/fluent-bit:latest
    volumeMounts:
      - name: varlog
        mountPath: /var/log
        readOnly: true

volumes:
  - name: varlog
    hostPath:
      path: /var/log
```

### ConfigMaps

```yaml
additionalConfigMaps:
  - name: app-config
    data:
      app.properties: |
        server.port=8080
        database.url=jdbc:postgresql://db:5432/myapp
    labels:
      app.kubernetes.io/component: config
  - name: nginx-config
    data:
      nginx.conf: |
        server {
          listen 80;
          location / {
            proxy_pass http://backend:8080;
          }
        }
```

### Secrets

Create Kubernetes Secrets with automatic base64 encoding:

```yaml
additionalSecrets:
  # Using stringData (auto base64-encoded)
  - name: app-secrets
    type: Opaque
    stringData:
      username: admin
      password: secret-password
      api-key: my-api-key-123
    labels:
      app: myapp
    annotations:
      description: "Application secrets"
  
  # Using pre-encoded data
  - name: tls-secret
    type: kubernetes.io/tls
    data:
      tls.crt: LS0tLS1CRUdJTi...  # base64 encoded
      tls.key: LS0tLS1CRUdJTi...  # base64 encoded
  
  # Optional namespace
  - name: cross-namespace-secret
    namespace: other-namespace
    type: Opaque
    stringData:
      shared-key: shared-value
```

### CronJobs

Create scheduled jobs with full CronJob specification:

```yaml
additionalCronJobs:
  - name: backup-job
    schedule: "0 2 * * *"  # Daily at 2 AM
    concurrencyPolicy: Forbid
    successfulJobsHistoryLimit: 3
    failedJobsHistoryLimit: 1
    jobTemplate:
      backoffLimit: 3
      template:
        restartPolicy: OnFailure
        serviceAccountName: backup-sa  # Optional, defaults to chart's serviceAccount
        containers:
        - name: backup
          image: backup-tool:latest
          command: ["/bin/sh", "-c"]
          args: ["backup.sh /data /backups"]
          env:
          - name: BACKUP_PATH
            value: "/backups"
          - name: DATABASE_URL
            valueFrom:
              secretKeyRef:
                name: db-secret
                key: url
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
          volumeMounts:
          - name: backup-storage
            mountPath: /backups
        volumes:
        - name: backup-storage
          persistentVolumeClaim:
            claimName: backup-pvc
        nodeSelector:
          workload-type: batch
```

### Additional Resources

Create any Kubernetes resource using structured format or raw YAML:

#### Structured Format (Recommended)

```yaml
additionalResources:
  - apiVersion: v1
    kind: PersistentVolumeClaim
    name: data-pvc
    spec:
      accessModes:
        - ReadWriteOnce
      storageClassName: fast-ssd
      resources:
        requests:
          storage: 10Gi
    labels:
      app: myapp
  
  - apiVersion: v1
    kind: Service
    name: external-service
    spec:
      type: ExternalName
      externalName: external.example.com
      ports:
      - port: 80
        targetPort: 8080
```

#### Raw YAML Format (For Complex Resources)

```yaml
additionalResources:
  # NetworkPolicy example
  - |
    apiVersion: networking.k8s.io/v1
    kind: NetworkPolicy
    metadata:
      name: allow-app
    spec:
      podSelector:
        matchLabels:
          app: myapp
      policyTypes:
      - Ingress
      - Egress
      ingress:
      - from:
        - podSelector:
            matchLabels:
              app: frontend
        ports:
        - protocol: TCP
          port: 8080
  
  # Role and RoleBinding example
  - |
    apiVersion: rbac.authorization.k8s.io/v1
    kind: Role
    metadata:
      name: pod-reader
    rules:
    - apiGroups: [""]
      resources: ["pods"]
      verbs: ["get", "watch", "list"]
  
  - |
    apiVersion: rbac.authorization.k8s.io/v1
    kind: RoleBinding
    metadata:
      name: read-pods
    subjects:
    - kind: ServiceAccount
      name: my-service-account
      namespace: default
    roleRef:
      kind: Role
      name: pod-reader
      apiGroup: rbac.authorization.k8s.io
```

**Note**: Raw YAML supports Helm template functions, so you can use `{{ .Release.Name }}`, `{{ .Values.* }}`, etc.

### Security Configuration

```yaml
serviceAccount:
  create: true
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/MyServiceRole

podSecurityContext:
  runAsNonRoot: true
  runAsUser: 1000
  fsGroup: 2000

securityContext:
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  capabilities:
    drop:
      - ALL

podDisruptionBudget:
  enabled: true
  minAvailable: 1
```

### Multi-Environment Configuration

Use global values for shared configuration across environments:

```yaml
global:
  image:
    repository: registry.flawlessbyte.dev/myapp
    pullPolicy: IfNotPresent
  additionalLabels:
    team: platform
    cost-center: engineering
  nodeSelector:
    node-type: application
  tolerations:
    - key: "application"
      operator: "Equal"
      value: "true"
      effect: "NoSchedule"
```

### Common Labels and Annotations

Apply labels and annotations to all resources:

```yaml
# Common labels applied to all resources
commonLabels:
  environment: production
  team: platform
  region: us-east-1
  cost-center: engineering

# Common annotations applied to all resources
commonAnnotations:
  argocd.argoproj.io/sync-wave: "3"
  description: "Production deployment"

# Global labels (merged with commonLabels, commonLabels takes precedence)
global:
  additionalLabels:
    global-label: value
```

### Container Name Configuration

Customize the main container name:

```yaml
# Default: Uses release name
# Example: release "my-app" → container name "my-app"

# Custom container name
containerName: "api-server"

# Works independently of nameOverride and fullnameOverride
nameOverride: "myapp"        # Affects resource names and labels
fullnameOverride: "custom"    # Affects resource names only
containerName: "web-server"   # Affects container name only
```

### Name Overrides

Control resource naming:

```yaml
# Override the chart name (affects labels and resource names)
nameOverride: "myapp"
# Result: Resources named "release-myapp", labels use "myapp"

# Override the full resource name
fullnameOverride: "custom-name"
# Result: All resources named "custom-name"

# Container name (independent of overrides)
containerName: "api-server"
# Result: Container named "api-server" regardless of overrides
```

## Configuration Reference

### Image Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `image.repository` | Container image repository | `"nginx"` |
| `image.tag` | Container image tag | `"latest"` |
| `image.pullPolicy` | Image pull policy | `"IfNotPresent"` |
| `image.pullSecrets` | Image pull secrets | `[]` |

### Workload Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `workload.enabled` | Enable workload creation | `true` |
| `workload.kind` | Workload type (Deployment/StatefulSet) | `"Deployment"` |
| `workload.replicaCount` | Number of replicas | `1` |
| `containerName` | Name of the main container | `""` (defaults to release name) |
| `nameOverride` | Override the chart name | `""` |
| `fullnameOverride` | Override the full resource name | `""` |
| `commonLabels` | Common labels applied to all resources | `{}` |
| `commonAnnotations` | Common annotations applied to all resources | `{}` |

### Service Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `service.enabled` | Enable service creation | `false` |
| `service.type` | Service type | `"ClusterIP"` |
| `service.ports` | Service ports configuration | `[]` |

### Auto-scaling Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `autoscaling.enabled` | Enable autoscaling | `false` |
| `autoscaling.type` | Autoscaler type (hpa/keda) | `"hpa"` |
| `autoscaling.minReplicas` | Minimum replicas | `1` |
| `autoscaling.maxReplicas` | Maximum replicas | `1` |

### External Secrets Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `externalSecrets.enabled` | Enable external secrets | `false` |
| `externalSecrets.name` | Custom secret name (optional) | `""` |
| `externalSecrets.annotations` | Custom annotations for external secret | `{}` |
| `externalSecrets.secretStoreRef.name` | Secret store name | `"aws-secrets-manager-store"` |
| `externalSecrets.secretStoreRef.kind` | Secret store kind | `"ClusterSecretStore"` |

### Additional Resources Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `additionalConfigMaps` | Array of ConfigMaps to create | `[]` |
| `additionalSecrets` | Array of Secrets to create | `[]` |
| `additionalCronJobs` | Array of CronJobs to create | `[]` |
| `additionalResources` | Array of generic Kubernetes resources (structured or raw YAML) | `[]` |
| `containerName` | Name of the main container | `""` (defaults to release name) |
| `commonLabels` | Common labels applied to all resources | `{}` |
| `commonAnnotations` | Common annotations applied to all resources | `{}` |

#### Additional Secrets Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `additionalSecrets[].name` | Secret name (required) | `""` |
| `additionalSecrets[].type` | Secret type | `"Opaque"` |
| `additionalSecrets[].namespace` | Optional namespace | `""` |
| `additionalSecrets[].stringData` | Secret data (auto base64-encoded) | `{}` |
| `additionalSecrets[].data` | Pre-encoded base64 secret data | `{}` |
| `additionalSecrets[].labels` | Additional labels | `{}` |
| `additionalSecrets[].annotations` | Additional annotations | `{}` |

#### Additional CronJobs Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `additionalCronJobs[].name` | CronJob name (required) | `""` |
| `additionalCronJobs[].schedule` | Cron schedule expression (required) | `""` |
| `additionalCronJobs[].concurrencyPolicy` | Concurrency policy (Allow/Forbid/Replace) | `""` |
| `additionalCronJobs[].suspend` | Suspend the CronJob | `false` |
| `additionalCronJobs[].successfulJobsHistoryLimit` | Number of successful jobs to keep | `3` |
| `additionalCronJobs[].failedJobsHistoryLimit` | Number of failed jobs to keep | `1` |
| `additionalCronJobs[].jobTemplate.backoffLimit` | Number of retries before marking as failed | `6` |
| `additionalCronJobs[].jobTemplate.template` | Pod template specification | `{}` |

## Examples

### Simple Web Application

```bash
helm install webapp nucleus/nucleus \
  --set image.repository=nginx \
  --set image.tag=1.21 \
  --set service.enabled=true \
  --set service.ports[0].name=http \
  --set service.ports[0].port=80 \
  --set service.ports[0].targetPort=80
```

### Microservice with Auto-scaling

```bash
helm install api nucleus/nucleus -f - <<EOF
image:
  repository: myapi
  tag: v1.2.3

service:
  enabled: true
  ports:
    - name: http
      port: 8080
      targetPort: 8080

autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 20
  hpa:
    targetCPUUtilizationPercentage: 70

resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 500m
    memory: 512Mi
EOF
```

### Database with Persistent Storage

```bash
helm install database nucleus/nucleus -f - <<EOF
workload:
  kind: StatefulSet

image:
  repository: postgres
  tag: "13"

env:
  - name: POSTGRES_DB
    value: myapp
  - name: POSTGRES_USER
    value: postgres
  - name: POSTGRES_PASSWORD
    valueFrom:
      secretKeyRef:
        name: db-secret
        key: password

volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 20Gi

volumeMounts:
  - name: data
    mountPath: /var/lib/postgresql/data

service:
  enabled: true
  ports:
    - name: postgres
      port: 5432
      targetPort: 5432
EOF
```

## Troubleshooting

### Common Issues

1. **Image Pull Errors**: Ensure image repository and credentials are correct
2. **Service Not Accessible**: Check service configuration and port mappings
3. **Pod Scheduling Issues**: Verify node selectors and resource requests
4. **External Secrets Not Working**: Confirm External Secrets Operator is installed and secret store is configured

### Debugging Commands

```bash
# Check pod status
kubectl get pods -l app.kubernetes.io/instance=my-app

# View pod logs
kubectl logs -l app.kubernetes.io/instance=my-app

# Describe pod for events
kubectl describe pod -l app.kubernetes.io/instance=my-app

# Check service endpoints
kubectl get endpoints my-app

# View external secret status
kubectl describe externalsecret my-app-external-secret
```

## CI/CD Pipeline

This repository includes a GitHub Actions workflow that:

### On Pull Requests
- Lints and validates the Helm chart
- Runs chart-testing with kind cluster
- Ensures chart can be installed successfully

### On Main Branch Push
- Packages the Helm chart
- Publishes to GitHub Pages
- Updates the Helm repository index

### On Release
- Creates a new chart release
- Publishes to GitHub Pages with versioning

The chart is automatically available at `https://flawlessbyte.github.io/nucleus` after successful builds.

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Test locally using the commands in the Local Development section
4. Commit your changes (`git commit -m 'Add some amazing feature'`)
5. Push to the branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For support and questions:
- Create an issue in the GitHub repository
- Contact the maintainer via GitHub Issues
- Check the documentation in the repository
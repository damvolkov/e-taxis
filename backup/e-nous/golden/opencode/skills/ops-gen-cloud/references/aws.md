# aws — capability → service map

Read the capability, take the service. Prefer the ones that speak an open interface (marked ✓ portable) — they keep the escape hatch open.

| Capability | AWS service | Portable | Note |
|---|---|---|---|
| Managed Kubernetes | EKS | ✓ (K8s API) | portable; the safe default for compute |
| Serverless containers | Fargate / App Runner | ~ | no node management; some lock-in |
| Functions | Lambda | ✗ | event glue; deep lock-in, cold starts |
| Object storage | S3 | ✓ (S3 API) | the de-facto standard; cheap, egress is the cost |
| Relational DB | RDS / Aurora (Postgres) | ✓ (Postgres wire) | Aurora is faster but more proprietary |
| Cache | ElastiCache (Valkey/Redis) | ✓ (Redis proto) | Valkey option at lower cost |
| Queue / streaming | SQS / MSK (Kafka) | SQS ✗ · MSK ✓ | MSK keeps the Kafka API |
| Vector | OpenSearch / Aurora pgvector | ~ | pgvector stays portable |
| Load balancer | ALB (L7) / NLB (L4) | ✓ | wired to EKS via the AWS LB controller |
| Secrets | Secrets Manager / SSM | ✗ | reach via External Secrets Operator |
| Identity | IAM + IRSA/Pod Identity | ✗ | per-pod roles, OIDC — no static keys |
| CDN / edge | CloudFront | ✗ | egress + latency answer (trigger #8) |
| Registry | ECR | ✓ (OCI) | push the image from `ops-gen-containers` |

## Lock-in & cost watch

- **Egress** is the silent bill — keep traffic in-region and in-VPC.
- Lambda + DynamoDB + Step Functions is the most locked-in stack; EKS + S3 + RDS(Postgres) is the most portable.
- IAM is the security boundary — least privilege, IRSA/Pod Identity over long-lived keys.
- Provision it all with `ops-gen-iac` (the AWS provider), never the console.

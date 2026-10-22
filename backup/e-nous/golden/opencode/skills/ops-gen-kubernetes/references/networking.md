# networking — exposing and routing

## Service — stable addressing inside the cluster

Pods are ephemeral with changing IPs; a Service is a stable virtual IP + DNS name in front of a set of Pods (selected by label), load-balancing across them (L4).

| Type | Reach | Use |
|---|---|---|
| `ClusterIP` (default) | in-cluster only | service-to-service |
| `NodePort` | a port on every node | dev, or behind an external LB |
| `LoadBalancer` | cloud LB provisioned | external exposure on a managed cluster |
| `Headless` (`clusterIP: None`) | direct Pod DNS | StatefulSets, client-side balancing |

## Gateway API — external L7 routing (the current standard)

The **Gateway API** is GA (GatewayClass, Gateway, HTTPRoute, GRPCRoute, TLSRoute, ReferenceGrant) and is the recommended path for new clusters: richer routing, role separation (infra owns `Gateway`, app owns `HTTPRoute`), a standard extension model.

- `Ingress` remains stable but **feature-frozen** — new capability only lands in Gateway API. The community Ingress-NGINX reached end-of-life in 2026; new clusters should not start there.
- Implementations: Envoy Gateway, Traefik, Istio, or a cloud controller.

```yaml
kind: HTTPRoute
spec:
  parentRefs: [{ name: public-gateway }]
  hostnames: ["api.eager.dev"]
  rules:
    - matches: [{ path: { type: PathPrefix, value: /v1 } }]
      backendRefs: [{ name: api, port: 8012 }]
```

## NetworkPolicy

Default is flat: any Pod can reach any Pod. A `NetworkPolicy` restricts ingress/egress by label/namespace — apply least-privilege between tiers (only the API may reach the database). Requires a CNI that enforces them (Cilium, Calico).

## Load balancing in context

The Service/Gateway is the execution of the load-balancing pattern from `sys-gen-scaling` `patterns.md`; consistent-hashing, retries and outlier detection are gateway/mesh features, not app code.

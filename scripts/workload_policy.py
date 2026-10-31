"""Portable isolation rules consumed by the unmodified nucleus chart."""

import ipaddress


def network_policies(name, component, database_cidrs):
    for cidr in database_cidrs:
        network = ipaddress.ip_network(cidr, strict=True)
        if network.version != 4 or not network.is_private or network.prefixlen < 16:
            raise ValueError(
                "Database egress must use private IPv4 ranges /16 or narrower"
            )
    if not database_cidrs:
        raise ValueError("Database egress CIDRs are required")
    instance = f"{name}-{component}"
    selector = {"matchLabels": {"app.kubernetes.io/instance": instance}}
    backend = {
        "podSelector": {
            "matchLabels": {"app.kubernetes.io/instance": f"{name}-backend"}
        }
    }
    frontend = {
        "podSelector": {
            "matchLabels": {"app.kubernetes.io/instance": f"{name}-frontend"}
        }
    }
    dns = {
        "to": [
            {
                "namespaceSelector": {
                    "matchLabels": {"kubernetes.io/metadata.name": "kube-system"}
                },
                "podSelector": {"matchLabels": {"k8s-app": "kube-dns"}},
            },
            {"ipBlock": {"cidr": "169.254.20.10/32"}},
            {"ipBlock": {"cidr": "169.254.169.254/32"}},
        ],
        "ports": [{"port": 53, "protocol": protocol} for protocol in ("UDP", "TCP")],
    }
    ingress = (
        [
            {
                "ports": [
                    {"port": 8080, "protocol": "TCP"},
                    {"port": 8443, "protocol": "TCP"},
                ]
            }
        ]
        if component == "frontend"
        else [{"from": [frontend], "ports": [{"port": 8000, "protocol": "TCP"}]}]
    )
    egress = (
        [dns, {"to": [backend], "ports": [{"port": 8000, "protocol": "TCP"}]}]
        if component == "frontend"
        else [
            dns,
            {
                "to": [{"ipBlock": {"cidr": cidr}} for cidr in database_cidrs],
                "ports": [{"port": 5432, "protocol": "TCP"}],
            },
        ]
    )
    return [
        {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "name": instance,
            "spec": {
                "podSelector": selector,
                "policyTypes": ["Ingress", "Egress"],
                "ingress": ingress,
                "egress": egress,
            },
        }
    ]


def namespace_resources(namespace, name="idea-board", database_cidrs=None):
    result = {
        "apiVersion": "v1",
        "kind": "List",
        "items": [
            {
                "apiVersion": "v1",
                "kind": "Namespace",
                "metadata": {
                    "name": namespace,
                    "labels": {
                        "pod-security.kubernetes.io/enforce": "restricted",
                        "pod-security.kubernetes.io/enforce-version": "v1.33",
                        "pod-security.kubernetes.io/audit": "restricted",
                        "pod-security.kubernetes.io/warn": "restricted",
                    },
                },
            },
            {
                "apiVersion": "v1",
                "kind": "ResourceQuota",
                "metadata": {"name": "workload-budget", "namespace": namespace},
                "spec": {
                    "hard": {
                        "requests.cpu": "8",
                        "requests.memory": "8Gi",
                        "limits.cpu": "16",
                        "limits.memory": "8Gi",
                        "pods": "20",
                        "services.loadbalancers": "1",
                    }
                },
            },
            {
                "apiVersion": "networking.k8s.io/v1",
                "kind": "NetworkPolicy",
                "metadata": {"name": "default-deny", "namespace": namespace},
                "spec": {
                    "podSelector": {},
                    "policyTypes": ["Ingress", "Egress"],
                    "ingress": [],
                    "egress": [],
                },
            },
        ],
    }

    if database_cidrs is not None:
        for component in ("backend", "frontend"):
            for policy in network_policies(name, component, database_cidrs):
                policy["metadata"] = {
                    "name": policy.pop("name"),
                    "namespace": namespace,
                }
                result["items"].append(policy)
    return result

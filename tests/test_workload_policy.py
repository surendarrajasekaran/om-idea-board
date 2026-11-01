import unittest

from scripts.workload_policy import namespace_resources, network_policies


class WorkloadSecurityTests(unittest.TestCase):
    def test_namespace_enforces_restricted_and_bounded_resources(self):
        resources = namespace_resources("workboard-staging")["items"]
        self.assertEqual(
            resources[0]["metadata"]["labels"]["pod-security.kubernetes.io/enforce"],
            "restricted",
        )
        self.assertEqual(resources[1]["spec"]["hard"]["services.loadbalancers"], "1")
        self.assertEqual(resources[2]["spec"]["egress"], [])

    def test_backend_accepts_only_frontend_and_egresses_to_database_and_dns(self):
        policy = network_policies("workboard", "backend", ["10.90.21.0/24"])[0]["spec"]
        self.assertEqual(
            policy["ingress"][0]["from"][0]["podSelector"]["matchLabels"][
                "app.kubernetes.io/instance"
            ],
            "workboard-frontend",
        )
        self.assertEqual(
            policy["egress"][1]["to"], [{"ipBlock": {"cidr": "10.90.21.0/24"}}]
        )
        self.assertEqual(policy["egress"][1]["ports"][0]["port"], 5432)
        self.assertNotIn(
            80, [p["port"] for rule in policy["egress"] for p in rule["ports"]]
        )

    def test_public_or_unbounded_database_network_is_rejected(self):
        for cidrs in [
            [],
            ["0.0.0.0/0"],
            ["8.8.8.8/32"],
            ["10.0.0.0/8"],
            ["10.0.0.1/24"],
        ]:
            with self.subTest(cidrs=cidrs), self.assertRaises(ValueError):
                network_policies("test", "backend", cidrs)

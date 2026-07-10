import unittest

import dashboard
import dashboard_sidebar


class DashboardSidebarRouteTests(unittest.TestCase):
    def test_admin_sidebar_endpoints_exist(self):
        endpoints = {rule.endpoint for rule in dashboard.app.url_map.iter_rules()}
        linked = {
            endpoint
            for section in dashboard_sidebar.ADMIN_SECTIONS
            for _, endpoint, _ in section["links"]
        }
        self.assertFalse(sorted(linked - endpoints))


if __name__ == "__main__":
    unittest.main()

moved {
  from = google_project_service.api
  to   = module.network.google_project_service.api
}
moved {
  from = google_compute_network.app
  to   = module.network.google_compute_network.app
}
moved {
  from = google_compute_subnetwork.app
  to   = module.network.google_compute_subnetwork.app
}
moved {
  from = google_compute_router.app
  to   = module.network.google_compute_router.app
}
moved {
  from = google_compute_router_nat.app
  to   = module.network.google_compute_router_nat.app
}
moved {
  from = google_compute_global_address.sql
  to   = module.network.google_compute_global_address.sql
}
moved {
  from = google_service_networking_connection.sql
  to   = module.network.google_service_networking_connection.sql
}
moved {
  from = google_container_cluster.app
  to   = module.kubernetes.google_container_cluster.app
}
moved {
  from = random_password.database
  to   = module.postgres.random_password.database
}
moved {
  from = google_sql_database_instance.ideas
  to   = module.postgres.google_sql_database_instance.ideas
}
moved {
  from = google_sql_database.ideas
  to   = module.postgres.google_sql_database.ideas
}
moved {
  from = google_sql_user.ideas
  to   = module.postgres.google_sql_user.ideas
}

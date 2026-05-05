import 'package:http/http.dart' as http;

import 'dashboard_http_client_stub.dart'
    if (dart.library.html) 'dashboard_http_client_web.dart' as impl;

http.Client createDashboardHttpClient() => impl.createDashboardHttpClient();

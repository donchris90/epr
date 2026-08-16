import 'dart:io';

import 'package:drift/native.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

/// Opens (or creates) the on-device SQLite file backing [AppDatabase].
LazyDatabase openConnection() {
  return LazyDatabase(() async {
    final dir = await getApplicationDocumentsDirectory();
    final file = File(p.join(dir.path, 'siteforge_field.sqlite'));
    return NativeDatabase.createInBackground(file);
  });
}

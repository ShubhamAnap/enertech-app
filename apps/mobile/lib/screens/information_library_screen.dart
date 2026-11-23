import 'package:material_ui/material_ui.dart';

import '../theme/app_theme.dart';
import '../widgets/app_components.dart';

class InformationLibraryScreen extends StatelessWidget {
  const InformationLibraryScreen({super.key, required this.title, required this.icon});
  final String title;
  final IconData icon;

  @override
  Widget build(BuildContext context) => Scaffold(appBar: AppBar(title: Text(title)), body: ListView(padding: const EdgeInsets.all(20), children: [
    Text('Search $title by product or document name.', style: const TextStyle(color: AppColors.muted, fontSize: 13)),
    const SizedBox(height: 14),
    TextField(enabled: false, decoration: InputDecoration(prefixIcon: const Icon(Icons.search_rounded), hintText: '$title are not connected')),
    const SizedBox(height: 14),
    Card(child: EmptyState(icon: icon, title: 'No approved content available', message: 'Only documents and coverage information verified and published by EnerTech will appear here.')),
  ]));
}

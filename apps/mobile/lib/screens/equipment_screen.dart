import 'package:material_ui/material_ui.dart';

import '../theme/app_theme.dart';
import '../widgets/app_components.dart';

class EquipmentScreen extends StatelessWidget {
  const EquipmentScreen({super.key});

  @override
  Widget build(BuildContext context) => Scaffold(appBar: AppBar(title: const Text('My equipment')), body: ListView(padding: const EdgeInsets.all(20), children: [
    const Text('Keep registered equipment and its service history together.', style: TextStyle(color: AppColors.muted, fontSize: 13, height: 1.4)),
    const SizedBox(height: 16),
    const Card(child: EmptyState(icon: Icons.electrical_services_outlined, title: 'No equipment registered', message: 'Register equipment after customer accounts and verification are available. Warranty status will only be shown from verified records.')),
    const SizedBox(height: 12),
    const NoticeCard(message: 'Serial numbers, purchase details, and warranty information are not collected or inferred in this build.'),
    const SizedBox(height: 16),
    const FilledButton(onPressed: null, child: Text('Equipment registration not connected')),
  ]));
}

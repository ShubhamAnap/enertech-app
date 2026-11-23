import 'package:material_ui/material_ui.dart';

import '../theme/app_theme.dart';

class SectionTitle extends StatelessWidget {
  const SectionTitle({super.key, required this.title, this.actionLabel, this.onAction});
  final String title;
  final String? actionLabel;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) => Row(
    mainAxisAlignment: MainAxisAlignment.spaceBetween,
    children: [
      Text(title, style: const TextStyle(color: AppColors.ink, fontSize: 16, fontWeight: FontWeight.w700)),
      if (actionLabel != null)
        TextButton(onPressed: onAction, child: Text(actionLabel!, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700))),
    ],
  );
}

class EmptyState extends StatelessWidget {
  const EmptyState({super.key, required this.icon, required this.title, required this.message, this.actionLabel, this.onAction});
  final IconData icon;
  final String title;
  final String message;
  final String? actionLabel;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 30),
    child: Column(mainAxisSize: MainAxisSize.min, children: [
      Container(
        width: 54,
        height: 54,
        decoration: BoxDecoration(color: const Color(0xFFF1F6FA), borderRadius: BorderRadius.circular(17), border: Border.all(color: AppColors.border)),
        child: Icon(icon, color: AppColors.blue, size: 24),
      ),
      const SizedBox(height: 14),
      Text(title, textAlign: TextAlign.center, style: const TextStyle(color: AppColors.ink, fontWeight: FontWeight.w700, fontSize: 15)),
      const SizedBox(height: 6),
      ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 300),
        child: Text(message, textAlign: TextAlign.center, style: const TextStyle(color: AppColors.muted, fontSize: 13, height: 1.45)),
      ),
      if (actionLabel != null && onAction != null) ...[
        const SizedBox(height: 16),
        OutlinedButton(onPressed: onAction, child: Text(actionLabel!)),
      ],
    ]),
  );
}

class IntentCard extends StatelessWidget {
  const IntentCard({super.key, required this.icon, required this.title, required this.subtitle, required this.onTap});
  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Card(
    child: InkWell(
      borderRadius: BorderRadius.circular(16),
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.all(15),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Icon(icon, size: 21, color: AppColors.blue),
          const SizedBox(height: 10),
          Text(title, style: const TextStyle(color: AppColors.ink, fontWeight: FontWeight.w700, fontSize: 13)),
          const SizedBox(height: 3),
          Text(subtitle, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(color: AppColors.muted, fontSize: 11)),
        ]),
      ),
    ),
  );
}

class NoticeCard extends StatelessWidget {
  const NoticeCard({super.key, required this.message, this.icon = Icons.info_outline});
  final String message;
  final IconData icon;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(13),
    decoration: BoxDecoration(color: const Color(0xFFF0F8FD), border: Border.all(color: const Color(0xFFD4E8F5)), borderRadius: BorderRadius.circular(14)),
    child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Icon(icon, color: AppColors.blue, size: 18),
      const SizedBox(width: 9),
      Expanded(child: Text(message, style: const TextStyle(color: Color(0xFF41627D), fontSize: 12, height: 1.45))),
    ]),
  );
}

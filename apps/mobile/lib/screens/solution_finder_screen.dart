import 'package:material_ui/material_ui.dart';

import '../data/app_content_repository.dart';
import '../data/customer_requests_repository.dart';
import '../theme/app_theme.dart';
import '../widgets/app_components.dart';

class SolutionFinderScreen extends StatefulWidget {
  const SolutionFinderScreen({super.key, this.initialProducts});
  final String? initialProducts;

  @override
  State<SolutionFinderScreen> createState() => _SolutionFinderScreenState();
}

class _SolutionFinderScreenState extends State<SolutionFinderScreen> {
  static const _applications = [
    'Factory / Industrial machinery',
    'Office / Commercial',
    'Hospital / Medical equipment',
    'Server room / Data centre',
    'Home / Residential',
    'Solar / Battery storage',
    'Other',
  ];
  static const _defaultStepTitles = [
    'Where do you need power protection?',
    'What needs power?',
    'Do you know the capacity?',
    'Where is the project?',
    'When do you need it?',
  ];
  late final Future<Map<String, dynamic>> _publishedAppContent =
      AppContentRepository().loadPublished();
  int _step = 0;
  String? _application;
  String? _capacityKnown;
  bool _confirmedPreview = false;
  bool _submitting = false;
  String? _submitError;
  late final TextEditingController _loadController;
  final _capacityController = TextEditingController();
  final _quantityController = TextEditingController(text: '1');
  final _locationController = TextEditingController();
  final _timelineController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _loadController = TextEditingController(text: widget.initialProducts ?? '');
  }

  @override
  void dispose() {
    _loadController.dispose();
    _capacityController.dispose();
    _quantityController.dispose();
    _locationController.dispose();
    _timelineController.dispose();
    super.dispose();
  }

  void _continue() {
    if (_step == 0 && _application == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Choose the application that best fits, or select Other.',
          ),
        ),
      );
      return;
    }
    if (_step == 1 && _loadController.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Describe what you need to keep powered, or enter “Not sure”.',
          ),
        ),
      );
      return;
    }
    if (_step == 2 && _capacityKnown == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Choose whether you know the capacity.')),
      );
      return;
    }
    if (_step < 4) setState(() => _step++);
  }

  Future<void> _submit() async {
    if (!_confirmedPreview) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Confirm that you want to send this enquiry.'),
        ),
      );
      return;
    }
    setState(() {
      _submitting = true;
      _submitError = null;
    });
    try {
      final result = await CustomerRequestsRepository().submitQuote(
        application: _application ?? 'Other',
        equipment: _loadController.text.trim(),
        capacityKnown: _capacityKnown == 'known',
        capacity: _capacityController.text.trim(),
        quantity: int.tryParse(_quantityController.text) ?? 1,
        location: _locationController.text.trim(),
        timeline: _timelineController.text.trim(),
      );
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Enquiry submitted'),
          content: Text(
            'EnerTech has received your requirement. Track updates in My requests. Reference: ${result.id.substring(0, 8).toUpperCase()}',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Done'),
            ),
          ],
        ),
      );
      if (mounted) Navigator.pop(context);
    } catch (error) {
      setState(
        () =>
            _submitError = error.toString().replaceFirst('HttpException: ', ''),
      );
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Map<String, dynamic>>(
      future: _publishedAppContent,
      builder: (context, snapshot) {
        final config = snapshot.data?['solution_finder'] is Map
            ? snapshot.data!['solution_finder'] as Map
            : const <String, dynamic>{};
        final configuredApplications = config['application_options'];
        final applicationOptions = configuredApplications is List
            ? configuredApplications.whereType<String>().toList(growable: false)
            : _applications;
        final configuredTitles = config['step_titles'];
        final stepTitles =
            configuredTitles is List &&
                configuredTitles.length == _defaultStepTitles.length
            ? configuredTitles.whereType<String>().toList(growable: false)
            : _defaultStepTitles;
        return _buildScreen(
          context,
          applications: applicationOptions.isEmpty
              ? _applications
              : applicationOptions,
          titles: stepTitles,
          applicationPrompt:
              config['application_prompt'] as String? ??
              'Choose the application that best describes your requirement.',
          generalPrompt: config['general_prompt'] as String? ?? 'Share what you know. You can skip technical details you are unsure about.',
        );
      },
    );
  }

  Widget _buildScreen(
    BuildContext context, {
    required List<String> applications,
    required List<String> titles,
    required String applicationPrompt,
    required String generalPrompt,
  }) {
    return Scaffold(
      appBar: AppBar(title: const Text('Find a solution')),
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 4, 20, 10),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Text(
                        'Solution Finder',
                        style: TextStyle(
                          color: AppColors.navy,
                          fontWeight: FontWeight.w700,
                          fontSize: 14,
                        ),
                      ),
                      Text(
                        'Step ${_step + 1} of 5',
                        style: const TextStyle(
                          color: AppColors.muted,
                          fontSize: 11,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 10),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(5),
                    child: LinearProgressIndicator(
                      value: (_step + 1) / 5,
                      minHeight: 5,
                      backgroundColor: const Color(0xFFDCE7F0),
                      color: AppColors.blue,
                    ),
                  ),
                ],
              ),
            ),
            Expanded(
              child: ListView(
                padding: const EdgeInsets.fromLTRB(20, 8, 20, 20),
                children: [
                  Text(
                    titles[_step],
                    style: const TextStyle(
                      color: AppColors.ink,
                      fontSize: 21,
                      fontWeight: FontWeight.w800,
                      height: 1.2,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    _step == 0 ? applicationPrompt : generalPrompt,
                    style: const TextStyle(
                      color: AppColors.muted,
                      fontSize: 13,
                      height: 1.45,
                    ),
                  ),
                  const SizedBox(height: 18),
                  if (_step == 0)
                    ...applications.map(
                      (item) => Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: _OptionTile(
                          title: item,
                          selected: _application == item,
                          onTap: () => setState(() => _application = item),
                        ),
                      ),
                    )
                  else if (_step == 1) ...[
                    TextField(
                      controller: _loadController,
                      maxLines: 4,
                      textCapitalization: TextCapitalization.sentences,
                      decoration: const InputDecoration(
                        alignLabelWithHint: true,
                        labelText: 'Equipment or load',
                        hintText: 'For example, the equipment or process that needs backup',
                      ),
                    ),
                    const SizedBox(height: 10),
                    OutlinedButton.icon(
                      onPressed: () => _loadController.text = 'Not sure yet',
                      icon: const Icon(Icons.help_outline_rounded),
                      label: const Text('I am not sure yet'),
                    ),
                  ] else if (_step == 2) ...[
                    _OptionTile(
                      title: 'I know the capacity',
                      subtitle: 'Add a value and unit if available',
                      selected: _capacityKnown == 'known',
                      onTap: () => setState(() => _capacityKnown = 'known'),
                    ),
                    const SizedBox(height: 8),
                    _OptionTile(
                      title: 'Help me determine it',
                      subtitle: 'An expert can review your requirement',
                      selected: _capacityKnown == 'unknown',
                      onTap: () => setState(() => _capacityKnown = 'unknown'),
                    ),
                    if (_capacityKnown == 'known') ...[
                      const SizedBox(height: 12),
                      TextField(
                        controller: _capacityController,
                        keyboardType: TextInputType.text,
                        decoration: const InputDecoration(
                          labelText: 'Capacity (optional)',
                          hintText: 'Enter the value and unit shown in your documents',
                        ),
                      ),
                    ],
                    const SizedBox(height: 12),
                    TextField(
                      controller: _quantityController,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(
                        labelText: 'Quantity',
                        hintText: '1',
                      ),
                    ),
                  ] else if (_step == 3) ...[
                    TextField(
                      controller: _locationController,
                      textCapitalization: TextCapitalization.words,
                      decoration: const InputDecoration(
                        labelText: 'Project location (optional)',
                        hintText: 'City, state, or PIN code',
                      ),
                    ),
                    const SizedBox(height: 10),
                    const NoticeCard(
                      message: 'Add a site address only when needed for your enquiry. No location is sent from this preview.',
                    ),
                  ] else ...[
                    TextField(
                      controller: _timelineController,
                      textCapitalization: TextCapitalization.sentences,
                      decoration: const InputDecoration(
                        labelText: 'Expected timeline (optional)',
                        hintText: 'Share a preferred timeframe',
                      ),
                    ),
                    const SizedBox(height: 18),
                    const Text(
                      'Requirement summary',
                      style: TextStyle(
                        color: AppColors.ink,
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(14),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            _SummaryLine(
                              label: 'Application',
                              value: _application ?? 'Not provided',
                            ),
                            _SummaryLine(
                              label: 'Equipment or load',
                              value: _loadController.text.isEmpty
                                  ? 'Not provided'
                                  : _loadController.text,
                            ),
                            _SummaryLine(
                              label: 'Capacity',
                              value: _capacityKnown == 'known'
                                  ? (_capacityController.text.isEmpty
                                        ? 'Not entered'
                                        : _capacityController.text)
                                  : 'Needs expert review',
                            ),
                            _SummaryLine(
                              label: 'Quantity',
                              value: _quantityController.text,
                            ),
                            _SummaryLine(
                              label: 'Location',
                              value: _locationController.text.isEmpty
                                  ? 'Not provided'
                                  : _locationController.text,
                            ),
                            _SummaryLine(
                              label: 'Timeline',
                              value: _timelineController.text.isEmpty
                                  ? 'Not provided'
                                  : _timelineController.text,
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 12),
                    const NoticeCard(
                      message: 'Submitting sends this requirement to EnerTech for follow-up. Do not include passwords, payment details, or unrelated personal information.',
                    ),
                    CheckboxListTile(
                      contentPadding: EdgeInsets.zero,
                      value: _confirmedPreview,
                      onChanged: (value) =>
                          setState(() => _confirmedPreview = value ?? false),
                      title: const Text(
                        'I have reviewed this requirement and want to send it to EnerTech',
                        style: TextStyle(fontSize: 12),
                      ),
                      controlAffinity: ListTileControlAffinity.leading,
                    ),
                    if (_submitError != null)
                      Padding(
                        padding: const EdgeInsets.only(top: 6),
                        child: Text(
                          _submitError!,
                          style: const TextStyle(
                            color: Color(0xFF9A3029),
                            fontSize: 12,
                          ),
                        ),
                      ),
                  ],
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 8, 20, 14),
              child: Row(
                children: [
                  if (_step > 0) ...[
                    OutlinedButton(
                      onPressed: () => setState(() => _step--),
                      child: const Text('Back'),
                    ),
                    const SizedBox(width: 10),
                  ],
                  Expanded(
                    child: FilledButton(
                      onPressed: _step == 4
                          ? (_submitting ? null : _submit)
                          : _continue,
                      child: _submitting
                          ? const SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : Text(
                              _step == 4
                                  ? 'Submit enquiry'
                                  : _step == 3
                                  ? 'Review requirement'
                                  : 'Continue',
                            ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _OptionTile extends StatelessWidget {
  const _OptionTile({
    required this.title,
    required this.selected,
    required this.onTap,
    this.subtitle,
  });
  final String title;
  final String? subtitle;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Material(
    color: selected ? const Color(0xFFEAF3FA) : Colors.white,
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(13),
      side: BorderSide(
        color: selected ? AppColors.blue : AppColors.border,
        width: selected ? 1.4 : 1,
      ),
    ),
    child: InkWell(
      borderRadius: BorderRadius.circular(13),
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 12),
        child: Row(
          children: [
            Icon(
              selected
                  ? Icons.radio_button_checked_rounded
                  : Icons.radio_button_unchecked_rounded,
              size: 20,
              color: selected ? AppColors.blue : AppColors.muted,
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: const TextStyle(
                      color: AppColors.ink,
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  if (subtitle != null) ...[
                    const SizedBox(height: 3),
                    Text(
                      subtitle!,
                      style: const TextStyle(
                        color: AppColors.muted,
                        fontSize: 11,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    ),
  );
}

class _SummaryLine extends StatelessWidget {
  const _SummaryLine({required this.label, required this.value});
  final String label;
  final String value;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 7),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 92,
          child: Text(
            label,
            style: const TextStyle(color: AppColors.muted, fontSize: 11),
          ),
        ),
        Expanded(
          child: Text(
            value,
            style: const TextStyle(
              color: AppColors.ink,
              fontSize: 12,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
      ],
    ),
  );
}

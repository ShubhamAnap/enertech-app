import 'dart:io';

import 'package:image_picker/image_picker.dart';
import 'package:material_ui/material_ui.dart';

import '../data/customer_requests_repository.dart';
import '../theme/app_theme.dart';
import '../widgets/app_components.dart';

class ServiceRequestScreen extends StatefulWidget {
  const ServiceRequestScreen({super.key});

  @override
  State<ServiceRequestScreen> createState() => _ServiceRequestScreenState();
}

class _ServiceRequestScreenState extends State<ServiceRequestScreen> {
  static const int _maxPhotos = 4;

  final _formKey = GlobalKey<FormState>();
  final _picker = ImagePicker();
  final _model = TextEditingController();
  final _serial = TextEditingController();
  final _description = TextEditingController();
  final _location = TextEditingController();
  final List<XFile> _selectedPhotos = [];
  final Map<String, String> _uploadedUrlsByPath = {};

  String? _issue;
  bool _working = false;
  String? _progressLabel;
  String? _error;

  Future<void> _pickFromGallery() async {
    final remaining = _maxPhotos - _selectedPhotos.length;
    if (remaining <= 0) {
      setState(() => _error = 'You can attach up to $_maxPhotos photos.');
      return;
    }
    try {
      final picked = await _picker.pickMultiImage(
        maxWidth: 1600,
        maxHeight: 1600,
        imageQuality: 85,
      );
      if (!mounted || picked.isEmpty) return;
      final existingPaths = _selectedPhotos.map((p) => p.path).toSet();
      final additions = picked
          .where((file) => !existingPaths.contains(file.path))
          .take(remaining)
          .toList(growable: false);
      setState(() {
        _error = picked.length > remaining
            ? 'Attached $_maxPhotos photos maximum.'
            : null;
        _selectedPhotos.addAll(additions);
      });
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'Could not open photo gallery. Please try again.');
      }
    }
  }

  Future<void> _capturePhoto() async {
    if (_selectedPhotos.length >= _maxPhotos) {
      setState(() => _error = 'You can attach up to $_maxPhotos photos.');
      return;
    }
    try {
      final picked = await _picker.pickImage(
        source: ImageSource.camera,
        maxWidth: 1600,
        maxHeight: 1600,
        imageQuality: 85,
      );
      if (!mounted || picked == null) return;
      setState(() {
        _error = null;
        _selectedPhotos.add(picked);
      });
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'Camera unavailable. Try choosing a photo from gallery.');
      }
    }
  }

  void _removePhoto(int index) {
    final removed = _selectedPhotos.removeAt(index);
    _uploadedUrlsByPath.remove(removed.path);
    setState(() => _error = null);
  }

  Future<void> _submit() async {
    FocusScope.of(context).unfocus();
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _working = true;
      _progressLabel = _selectedPhotos.isNotEmpty
          ? 'Uploading photos…'
          : 'Submitting request…';
      _error = null;
    });
    final repo = CustomerRequestsRepository();
    try {
      final uploadedUrls = <String>[];
      for (var i = 0; i < _selectedPhotos.length; i++) {
        final photo = _selectedPhotos[i];
        final cachedUrl = _uploadedUrlsByPath[photo.path];
        if (cachedUrl != null) {
          uploadedUrls.add(cachedUrl);
          continue;
        }
        if (mounted) {
          setState(
            () => _progressLabel =
                'Uploading photo ${i + 1} of ${_selectedPhotos.length}…',
          );
        }
        final url = await repo.uploadServicePhoto(File(photo.path));
        _uploadedUrlsByPath[photo.path] = url;
        uploadedUrls.add(url);
      }
      if (mounted) {
        setState(() => _progressLabel = 'Submitting request…');
      }
      final result = await repo.submitService(
        model: _model.text.trim(),
        serial: _serial.text.trim().isEmpty ? null : _serial.text.trim(),
        category: _issue!,
        description: _description.text.trim(),
        location: _location.text.trim(),
        attachments: uploadedUrls,
      );
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Request submitted'),
          content: Text(
            'Your service request is recorded. Track it in My requests. Reference: ${result.id.substring(0, 8).toUpperCase()}',
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
    } on HttpException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } catch (_) {
      if (mounted) {
        setState(
          () => _error =
              'Could not send the service request. Check your connection and try again.',
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          _working = false;
          _progressLabel = null;
        });
      }
    }
  }

  @override
  void dispose() {
    _model.dispose();
    _serial.dispose();
    _description.dispose();
    _location.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('New service request')),
    body: SafeArea(
      child: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 28),
          children: [
            const Text(
              'Tell us about the equipment and issue.',
              style: TextStyle(color: AppColors.muted, fontSize: 13),
            ),
            const SizedBox(height: 16),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(15),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Equipment',
                      style: TextStyle(
                        color: AppColors.ink,
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 11),
                    TextFormField(
                      controller: _model,
                      textCapitalization: TextCapitalization.characters,
                      textInputAction: TextInputAction.next,
                      maxLength: 120,
                      validator: (value) => (value?.trim().isNotEmpty ?? false)
                          ? null
                          : 'Enter the product model.',
                      decoration: const InputDecoration(
                        labelText: 'Product model *',
                        hintText: 'Enter model name or number',
                      ),
                    ),
                    const SizedBox(height: 10),
                    TextFormField(
                      controller: _serial,
                      textCapitalization: TextCapitalization.characters,
                      textInputAction: TextInputAction.next,
                      maxLength: 120,
                      decoration: const InputDecoration(
                        labelText: 'Serial number (optional)',
                        hintText: 'Enter serial number if known',
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 10),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(15),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'What is happening?',
                      style: TextStyle(
                        color: AppColors.ink,
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 11),
                    DropdownButtonFormField<String>(
                      initialValue: _issue,
                      validator: (value) =>
                          value == null ? 'Choose the issue category.' : null,
                      decoration: const InputDecoration(
                        labelText: 'Issue category *',
                      ),
                      items: const [
                        DropdownMenuItem(
                          value: 'alarm',
                          child: Text('Alarm or fault'),
                        ),
                        DropdownMenuItem(
                          value: 'battery',
                          child: Text('Battery concern'),
                        ),
                        DropdownMenuItem(
                          value: 'performance',
                          child: Text('Performance issue'),
                        ),
                        DropdownMenuItem(
                          value: 'installation',
                          child: Text('Installation or maintenance'),
                        ),
                        DropdownMenuItem(value: 'other', child: Text('Other')),
                      ],
                      onChanged: _working
                          ? null
                          : (value) => setState(() => _issue = value),
                    ),
                    const SizedBox(height: 10),
                    TextFormField(
                      controller: _description,
                      minLines: 4,
                      maxLines: 6,
                      maxLength: 4000,
                      textCapitalization: TextCapitalization.sentences,
                      textInputAction: TextInputAction.next,
                      validator: (value) => (value?.trim().length ?? 0) >= 10
                          ? null
                          : 'Describe the issue in at least 10 characters.',
                      decoration: const InputDecoration(
                        alignLabelWithHint: true,
                        labelText: 'Describe the issue *',
                        hintText: 'What happened? When did it start?',
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 10),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(15),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Service location & photos',
                      style: TextStyle(
                        color: AppColors.ink,
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 11),
                    TextFormField(
                      controller: _location,
                      textCapitalization: TextCapitalization.words,
                      textInputAction: TextInputAction.done,
                      maxLength: 500,
                      validator: (value) => (value?.trim().length ?? 0) >= 2
                          ? null
                          : 'Enter a city, state, or PIN code.',
                      decoration: const InputDecoration(
                        labelText: 'City, state, or PIN code *',
                      ),
                    ),
                    const SizedBox(height: 12),
                    Text(
                      'Equipment / fault photos (${_selectedPhotos.length}/$_maxPhotos optional)',
                      style: const TextStyle(
                        color: AppColors.ink,
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        OutlinedButton.icon(
                          onPressed: _working || _selectedPhotos.length >= _maxPhotos
                              ? null
                              : _pickFromGallery,
                          icon: const Icon(Icons.photo_library_outlined, size: 18),
                          label: const Text('Choose photos'),
                        ),
                        OutlinedButton.icon(
                          onPressed: _working || _selectedPhotos.length >= _maxPhotos
                              ? null
                              : _capturePhoto,
                          icon: const Icon(Icons.photo_camera_outlined, size: 18),
                          label: const Text('Take photo'),
                        ),
                      ],
                    ),
                    if (_selectedPhotos.isNotEmpty) ...[
                      const SizedBox(height: 10),
                      Wrap(
                        spacing: 10,
                        runSpacing: 10,
                        children: [
                          for (var i = 0; i < _selectedPhotos.length; i++)
                            Stack(
                              clipBehavior: Clip.none,
                              children: [
                                ClipRRect(
                                  borderRadius: BorderRadius.circular(10),
                                  child: Image.file(
                                    File(_selectedPhotos[i].path),
                                    width: 74,
                                    height: 74,
                                    fit: BoxFit.cover,
                                  ),
                                ),
                                if (!_working)
                                  Positioned(
                                    top: -6,
                                    right: -6,
                                    child: GestureDetector(
                                      onTap: () => _removePhoto(i),
                                      child: Container(
                                        width: 22,
                                        height: 22,
                                        decoration: const BoxDecoration(
                                          color: AppColors.navy,
                                          shape: BoxShape.circle,
                                        ),
                                        child: const Icon(
                                          Icons.close_rounded,
                                          size: 14,
                                          color: Colors.white,
                                        ),
                                      ),
                                    ),
                                  ),
                              ],
                            ),
                        ],
                      ),
                    ],
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),
            const NoticeCard(
              message:
                  'Your request and attached photos are sent directly to EnerTech support when submitted. Do not include passwords, payment details, or unrelated personal information.',
            ),
            if (_error != null) ...[
              const SizedBox(height: 10),
              NoticeCard(message: _error!, icon: Icons.error_outline_rounded),
            ],
            const SizedBox(height: 15),
            FilledButton(
              onPressed: _working ? null : _submit,
              child: _working
                  ? Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        ),
                        const SizedBox(width: 10),
                        Text(_progressLabel ?? 'Submitting…'),
                      ],
                    )
                  : const Text('Submit service request'),
            ),
          ],
        ),
      ),
    ),
  );
}

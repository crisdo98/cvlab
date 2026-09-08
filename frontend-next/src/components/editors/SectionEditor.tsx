'use client';

import { useSectionForm } from '@/hooks/useSectionForm';
import { useSaveSectionContent } from '@/hooks/useSections';
import { CertificationEditor, EducationEditor } from './EntryEditors';
import { ExperienceEditor } from './ExperienceEditor';
import { FreeTextEditor, ListEditor, PersonalInfoEditor } from './SimpleEditors';
import type { Section, SectionContent } from '@/types/cv';

const PLACEHOLDER: Record<string, string> = {
  summary:
    'A short paragraph on what you do, the scale you operate at, and the outcomes you drive.',
};

const HINT: Record<string, string> = {
  skills: 'One skill or group per line.',
  languages: 'One language per line, with proficiency.',
  software: 'Tools and platforms you use.',
  interests: 'Keep this short.',
  websites: 'Portfolios, publications, profiles.',
};

/**
 * Routes a section to the right editor and owns its save lifecycle. One
 * component for every section type, at every screen width — the Vue app had an
 * inline editor for desktop and a modal for narrow, which was two code paths
 * for one job.
 */
export function SectionEditor({
  section,
  cvId,
  onClose,
}: {
  section: Section;
  cvId: string;
  onClose: () => void;
}) {
  const form = useSectionForm<SectionContent>(section.id, section.content);
  const save = useSaveSectionContent(cvId);

  const handleSave = async () => {
    await save.mutateAsync({ sectionId: section.id, content: form.content });
    form.markSaved();
  };

  const body = (() => {
    const kind = form.content.content_type;

    if (kind === 'personal') {
      return <PersonalInfoEditor form={form as never} />;
    }
    if (kind === 'free_text') {
      return (
        <FreeTextEditor
          form={form as never}
          placeholder={PLACEHOLDER[section.type]}
          hint={HINT[section.type]}
        />
      );
    }
    if (kind === 'list') {
      return <ListEditor form={form as never} hint={HINT[section.type]} />;
    }
    if (kind === 'structured') {
      if (section.type === 'experience') return <ExperienceEditor form={form as never} />;
      if (section.type === 'education') return <EducationEditor form={form as never} />;
      if (section.type === 'certifications')
        return <CertificationEditor form={form as never} />;
    }

    return (
      <div className="alert alert-warning">
        This section type has no editor yet ({section.type}).
      </div>
    );
  })();

  return (
    <div className="flex flex-col gap-4">
      {body}

      <div className="flex items-center gap-2 pb-2">
        {form.dirty && (
          <span className="flex items-center gap-1.5 text-warning-600">
            <span className="w-1.5 h-1.5 rounded-full bg-warning-400" />
            <span className="text-meta">Unsaved</span>
          </span>
        )}
        <div className="flex-1" />
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => {
            form.reset();
            onClose();
          }}
        >
          {form.dirty ? 'Discard' : 'Close'}
        </button>
        <button
          type="button"
          className="btn btn-primary"
          disabled={!form.dirty || save.isPending}
          onClick={() => void handleSave()}
        >
          {save.isPending ? 'Saving…' : 'Save section'}
        </button>
      </div>
    </div>
  );
}

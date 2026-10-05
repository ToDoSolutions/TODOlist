import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Box,
  Checkbox,
  FormControlLabel,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useTranslation } from "react-i18next";
import { customFieldsApi } from "../api/resources";
import type { CustomField, CustomFieldValue } from "../types";
import { notify } from "../notify";

/**
 * Campos personalizados de la tarea (por proyecto). Cada campo del
 * proyecto se renderiza según su tipo y se persiste al blur/change:
 *   - sin CFV → POST {task, field, value}
 *   - con CFV → PATCH {value} | DELETE si queda vacío
 *
 * Antes solo se podían editar escribiendo el id de la tarea a mano en
 * CustomFieldsPage.
 */
export default function TaskCustomFields({
  taskId,
  projectId,
}: {
  taskId: number;
  projectId: number;
}) {
  const { t } = useTranslation();
  const qc = useQueryClient();

  const { data: allFields } = useQuery({
    queryKey: ["custom-fields"],
    queryFn: customFieldsApi.list,
  });
  const fields: CustomField[] = ((allFields ?? []) as CustomField[]).filter(
    (f) => f.project === projectId,
  );

  const { data: valuesData } = useQuery({
    queryKey: ["custom-field-values", taskId],
    queryFn: () => customFieldsApi.values({ task: taskId }),
  });
  const cfvs: CustomFieldValue[] = Array.isArray(valuesData)
    ? valuesData
    : ((valuesData as { results?: CustomFieldValue[] } | undefined)?.results ??
      []);
  const byField = new Map(cfvs.map((v) => [v.field, v]));

  const invalidate = () =>
    qc.invalidateQueries({ queryKey: ["custom-field-values", taskId] });

  const save = useMutation({
    mutationFn: async ({
      field,
      value,
    }: {
      field: CustomField;
      value: unknown;
    }) => {
      const empty =
        value === "" || value === null || value === false ||
        (Array.isArray(value) && value.length === 0);
      const existing = byField.get(field.id);
      if (empty) {
        if (existing) await customFieldsApi.removeValue(existing.id);
        return;
      }
      if (existing) await customFieldsApi.updateValue(existing.id, value);
      else await customFieldsApi.setValue({ task: taskId, field: field.id, value });
    },
    onSuccess: invalidate,
    onError: () => notify.error(t("p.ops.cf.valueUpdateError")),
  });

  if (fields.length === 0) return null;

  return (
    <Box>
      <Typography
        variant="caption"
        color="text.secondary"
        fontWeight={700}
        display="block"
        mb={1}
      >
        {t("p.ops.cf.customFields")}
      </Typography>
      <Stack spacing={1.5}>
        {fields.map((f) => (
          <FieldInput
            key={f.id}
            field={f}
            cfv={byField.get(f.id)}
            onSave={(value) => save.mutate({ field: f, value })}
          />
        ))}
      </Stack>
    </Box>
  );
}

function FieldInput({
  field,
  cfv,
  onSave,
}: {
  field: CustomField;
  cfv: CustomFieldValue | undefined;
  onSave: (value: unknown) => void;
}) {
  const ftype = field.field_type ?? field.type ?? "text";
  const options: string[] = Array.isArray(field.options) ? field.options : [];

  const asText = (): string =>
    cfv?.value == null
      ? ""
      : typeof cfv.value === "string"
        ? cfv.value
        : JSON.stringify(cfv.value);

  const [draft, setDraft] = useState<string | null>(null);
  const shown = draft ?? asText();
  const commit = (v: string) => {
    if (v !== asText()) onSave(ftype === "number" && v !== "" ? Number(v) : v);
    setDraft(null);
  };

  switch (ftype) {
    case "number":
      return (
        <TextField
          size="small"
          label={field.name}
          type="number"
          fullWidth
          value={shown}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={() => commit(shown)}
        />
      );
    case "date":
      return (
        <TextField
          size="small"
          label={field.name}
          type="date"
          fullWidth
          InputLabelProps={{ shrink: true }}
          value={shown.slice(0, 10)}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={() => commit(shown.slice(0, 10))}
        />
      );
    case "url":
      return (
        <TextField
          size="small"
          label={field.name}
          type="url"
          fullWidth
          placeholder="https://…"
          value={shown}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={() => commit(shown)}
        />
      );
    case "checkbox":
      return (
        <FormControlLabel
          control={
            <Checkbox
              size="small"
              checked={cfv?.value === true}
              onChange={(e) => onSave(e.target.checked)}
            />
          }
          label={field.name}
        />
      );
    case "select":
      return (
        <TextField
          select
          size="small"
          label={field.name}
          fullWidth
          value={shown}
          onChange={(e) => onSave(e.target.value)}
          SelectProps={{ native: true }}
        >
          <option value="" />
          {options.map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </TextField>
      );
    case "multiselect": {
      const current: string[] = Array.isArray(cfv?.value)
        ? (cfv.value as string[])
        : [];
      return (
        <Box>
          <Typography variant="body2" color="text.secondary">
            {field.name}
          </Typography>
          <Stack direction="row" flexWrap="wrap" useFlexGap>
            {options.map((o) => (
              <FormControlLabel
                key={o}
                control={
                  <Checkbox
                    size="small"
                    checked={current.includes(o)}
                    onChange={(e) =>
                      onSave(
                        e.target.checked
                          ? [...current, o]
                          : current.filter((x) => x !== o),
                      )
                    }
                  />
                }
                label={o}
              />
            ))}
          </Stack>
        </Box>
      );
    }
    default:
      return (
        <TextField
          size="small"
          label={field.name}
          fullWidth
          value={shown}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={() => commit(shown)}
        />
      );
  }
}

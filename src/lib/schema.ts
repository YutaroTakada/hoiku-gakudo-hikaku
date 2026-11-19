import { z } from "zod";
import { AREA_IDS, CATEGORY_IDS, MANAGEMENTS, TYPE_IDS, typeCategory, typeMapEnabled } from "../config/site";

/** 出どころと確認日つきの値。value が null のものはサイト上で「未確認」と出す。 */
const isoDate = z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "確認日は YYYY-MM-DD");
const field = <T extends z.ZodTypeAny>(t: T) =>
  z
    .object({
      value: t.nullable(),
      source: z.string().url().nullable(),
      checked: isoDate.nullable(),
      note: z.string().optional(),
    })
    .strict()
    .superRefine((f, ctx) => {
      if (f.value !== null && (!f.source || !f.checked)) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, message: "値があるのに出どころか確認日がない" });
      }
    });

const time = z.string().regex(/^\d{1,2}:\d{2}$/);
const range = z.object({ min: z.number().int().min(0).max(6), max: z.number().int().min(0).max(6) }).strict();
const vacancy = z
  .object({
    byAge: z.record(z.string().regex(/^[0-6]$/), z.number().int().min(0).nullable()).nullable(),
    total: z.number().int().min(0).nullable(),
    totalText: z.string().nullable().optional(),
    label: z.string(),
    asOf: isoDate.nullable(),
  })
  .strict();

export type FacilityType = string;

/** 施設 id：<エリア>-<種別>-<8桁の16進>。エリアと種別は設定から作る。 */
const esc = (x: string) => x.replace(/[^a-z0-9_]/g, "");
const idPattern = new RegExp(`^(${AREA_IDS.map(esc).join("|")})-(${TYPE_IDS.map(esc).join("|")})-[0-9a-f]{8}$`);

export const facilitySchema = z
  .object({
    id: z.string().regex(idPattern),
    ward: z.enum(AREA_IDS),
    category: z.enum(CATEGORY_IDS),
    type: z.enum(TYPE_IDS),
    management: z.enum(MANAGEMENTS),
    name: z.string().min(1),
    listedName: z.string().min(1),
    address: field(z.string()),
    location: field(z.object({ lat: z.number().finite().min(-90).max(90), lng: z.number().finite().min(-180).max(180), level: z.literal("block"), matched: z.string().min(1) }).strict()),
    image: field(z.object({ kind: z.literal("map"), path: z.string().regex(/^\/img\/map\/[a-z0-9_-]+\.webp$/), width: z.literal(480), height: z.literal(240) }).strict()),
    station: field(z.string()),
    phone: field(z.string()),
    ages: field(z.string()),
    ageRange: field(range),
    capacity: field(z.number().int().positive()),
    hours: z
      .object({
        weekday: field(z.string()),
        weekdayEnd: field(time),
        extension: field(z.string()),
        extensionEnd: field(time),
        saturday: field(z.string()),
        vacation: field(z.string()).optional(),
      })
      .strict(),
    fees: z
      .object({
        table: field(z.string().url()).optional(),
        basic: field(z.string()).optional(),
        own: field(z.string()).optional(),
        extensionFee: field(z.string()).optional(),
        monthly: field(z.number().int().min(0)).optional(),
        snack: field(z.number().int().min(0)).optional(),
        extension: field(z.string()).optional(),
      })
      .strict(),
    pickup: field(z.string()),
    vacancy: field(vacancy),
    application: z.object({ method: field(z.string()), deadline: field(z.string()) }).strict(),
    links: z.object({ official: field(z.string().url()), intro: field(z.string().url()) }).strict(),
    operator: field(z.string()).optional(),
    notice: field(z.string()).optional(),
  })
  .strict()
  .superRefine((f, ctx) => {
    if ((f.location.value === null) !== (f.image.value === null)) ctx.addIssue({ code: z.ZodIssueCode.custom, message: "位置と画像が一致しない" });
    if (!typeMapEnabled(f.type) && (f.location.value || f.image.value)) ctx.addIssue({ code: z.ZodIssueCode.custom, message: "この種別に地図は表示できません" });
    if (f.image.value && f.image.value.path !== `/img/map/${f.id}.webp`) ctx.addIssue({ code: z.ZodIssueCode.custom, message: "画像パスと id が一致しない" });
    if (!f.id.startsWith(`${f.ward}-${f.type}-`)) ctx.addIssue({ code: z.ZodIssueCode.custom, message: "id と区・種別が合わない" });
    if (typeCategory(f.type) !== f.category) ctx.addIssue({ code: z.ZodIssueCode.custom, message: "種別と category が合わない" });
  });

export type Facility = z.infer<typeof facilitySchema>;
export type Field<T> = { value: T | null; source: string | null; checked: string | null; note?: string };

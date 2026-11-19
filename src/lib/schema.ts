import { z } from "zod";

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

export const TYPES = {
  ninka: "認可保育所",
  kodomoen: "認定こども園",
  shokibo: "小規模保育",
  jigyosho: "事業所内保育",
  katei: "家庭的保育（保育ママ）",
  ninsho: "東京都認証保育所",
  gakudo_ku: "区の学童（公設）",
  gakudo_min: "民設の学童",
  houkago: "放課後子ども教室",
} as const;
export type FacilityType = keyof typeof TYPES;

export const facilitySchema = z
  .object({
    id: z.string().regex(/^(adachi|taito)-[a-z_]+-[0-9a-f]{8}$/),
    ward: z.enum(["adachi", "taito"]),
    category: z.enum(["hoiku", "gakudo"]),
    type: z.enum(Object.keys(TYPES) as [FacilityType, ...FacilityType[]]),
    management: z.enum(["公立", "公設民営", "民間"]),
    name: z.string().min(1),
    listedName: z.string().min(1),
    address: field(z.string()),
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
    if (!f.id.startsWith(`${f.ward}-${f.type}-`)) ctx.addIssue({ code: z.ZodIssueCode.custom, message: "id と区・種別が合わない" });
    const isGakudo = ["gakudo_ku", "gakudo_min", "houkago"].includes(f.type);
    if (isGakudo !== (f.category === "gakudo")) ctx.addIssue({ code: z.ZodIssueCode.custom, message: "種別と category が合わない" });
  });

export type Facility = z.infer<typeof facilitySchema>;
export type Field<T> = { value: T | null; source: string | null; checked: string | null; note?: string };

// SPDX-License-Identifier: GPL-2.0
/*
 * mdppoke - MDP5 寄存器在线读写与实时状态观测（仅用于调试）
 *
 * 用法：
 *   modprobe mdppoke                                    # 只观测
 *   modprobe mdppoke pokes="6a804=80000000"             # 先写再观测
 *   modprobe mdppoke pokes="6a804=80000000,1014=1f20"   # 多组写入
 */
#include <linux/module.h>
#include <linux/io.h>
#include <linux/delay.h>
#include <linux/kernel.h>
#include <linux/string.h>

#define MDP_BASE_PHYS	0x1a01000UL
#define MDP_MAP_SIZE	0x80000UL

#define OFF_CTL0	0x01000
#define OFF_LM0		0x44000
#define OFF_INTF1	0x6a800
#define OFF_PP0		0x70000

static void __iomem *base;
static char *pokes = "";
module_param(pokes, charp, 0444);
MODULE_PARM_DESC(pokes, "comma separated off=val pairs in hex");

static char *dumps = "";
module_param(dumps, charp, 0444);
MODULE_PARM_DESC(dumps, "comma separated phys:size regions to dump, hex");

static char *physpokes = "";
module_param(physpokes, charp, 0444);
MODULE_PARM_DESC(physpokes, "comma separated physaddr=val pairs, hex");

static u32 rd(u32 off)
{
	return readl(base + off);
}

static void wr(u32 off, u32 val)
{
	writel(val, base + off);
}

static void do_pokes(void)
{
	char buf[256];
	char *p = buf, *q;
	u32 off, val, old;

	if (!pokes || !*pokes)
		return;

	strscpy(buf, pokes, sizeof(buf));
	while (*p) {
		if (sscanf(p, "%x=%x", &off, &val) != 2)
			break;
		old = rd(off);
		wr(off, val);
		pr_info("MDPPOKE off=0x%05x : %08x -> %08x (readback %08x)\n",
			off, old, val, rd(off));
		q = strchr(p, ',');
		if (!q)
			break;
		p = q + 1;
	}
}

static void report(const char *when)
{
	pr_info("MDPPOKE [%s] cfg=0x%08x panel_fmt=0x%08x flc_en=0x%08x frame_cnt=%u line_cnt=%u ctl_op=0x%08x\n",
		when, rd(OFF_INTF1 + 0x04), rd(OFF_INTF1 + 0x90),
		rd(OFF_INTF1 + 0xa8), rd(OFF_INTF1 + 0xac),
		rd(OFF_INTF1 + 0xb0), rd(OFF_CTL0 + 0x14));
	pr_info("MDPPOKE [%s] ctl_layer=0x%08x lm_blend(st0,1,2)=%08x/%08x/%08x pp0_lines=%u pp0_out=%u\n",
		when, rd(OFF_CTL0 + 0x00),
		rd(OFF_LM0 + 0x20), rd(OFF_LM0 + 0x50), rd(OFF_LM0 + 0x80),
		rd(OFF_PP0 + 0x2c), rd(OFF_PP0 + 0x28));
}

static void do_dumps(void)
{
	char buf[256];
	char *p = buf, *q;
	unsigned long phys, size;
	unsigned long off;
	void __iomem *m;
	int i;

	if (!dumps || !*dumps)
		return;

	strscpy(buf, dumps, sizeof(buf));
	while (*p) {
		if (sscanf(p, "%lx:%lx", &phys, &size) != 2)
			break;
		if (size > 0x4000)
			size = 0x4000;
		m = ioremap(phys, size);
		if (!m) {
			pr_err("MDPPOKE dump ioremap 0x%lx failed\n", phys);
		} else {
			for (off = 0; off + 3 < size / 4; off += 4) {
				pr_info("MDPDUMP %08lx +%03lx: %08x %08x %08x %08x\n",
					phys, off * 4,
					readl(m + (off + 0) * 4), readl(m + (off + 1) * 4),
					readl(m + (off + 2) * 4), readl(m + (off + 3) * 4));
				if (off > 1024)
					break;
			}
			iounmap(m);
		}
		q = strchr(p, ',');
		if (!q)
			break;
		p = q + 1;
	}
	(void)i;
}

static void do_physpokes(void)
{
	char buf[256];
	char *p = buf, *q;
	unsigned long phys, val;
	void __iomem *m;

	if (!physpokes || !*physpokes)
		return;

	strscpy(buf, physpokes, sizeof(buf));
	while (*p) {
		if (sscanf(p, "%lx=%lx", &phys, &val) != 2)
			break;
		m = ioremap(phys & ~0xfffUL, 0x1000);
		if (!m) {
			pr_err("MDPPOKE phys ioremap 0x%lx failed\n", phys);
		} else {
			u32 old = readl(m + (phys & 0xfff));

			writel((u32)val, m + (phys & 0xfff));
			pr_info("MDPPOKE phys 0x%lx : %08x -> %08x (rb %08x)\n",
				phys, old, (u32)val,
				readl(m + (phys & 0xfff)));
			iounmap(m);
		}
		q = strchr(p, ',');
		if (!q)
			break;
		p = q + 1;
	}
}

static int __init mdppoke_init(void)
{
	base = ioremap(MDP_BASE_PHYS, MDP_MAP_SIZE);
	if (!base) {
		pr_err("MDPPOKE ioremap failed\n");
		return -ENOMEM;
	}

	report("before");
	do_dumps();
	do_pokes();
	do_physpokes();

	msleep(200);
	report("t0");
	msleep(400);
	report("t1");
	msleep(400);
	report("t2");
	return 0;
}

static void __exit mdppoke_exit(void)
{
	if (base)
		iounmap(base);
}

module_init(mdppoke_init);
module_exit(mdppoke_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("MDP5 register poke/observe tool");

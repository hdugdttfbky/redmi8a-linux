// SPDX-License-Identifier: GPL-2.0-only
/*
 * Xiaomi Redmi 8A (olivelite) - Novatek NT36525B, 720x1520 video mode
 *
 * 时序与初始化序列取自原厂 dtbo（dtbobak 分区备份）中的
 * qcom,mdss_dsi_nvt36525b_hdplus_video_c3i 节点。
 */

#include <linux/delay.h>
#include <linux/gpio/consumer.h>
#include <linux/mod_devicetable.h>
#include <linux/module.h>

#include <drm/drm_mipi_dsi.h>
#include <drm/drm_modes.h>
#include <drm/drm_panel.h>
#include <drm/drm_probe_helper.h>

struct nt36525b {
	struct drm_panel panel;
	struct mipi_dsi_device *dsi;
	struct gpio_desc *reset_gpio;
};

/*
 * Clock-lane mode is runtime switchable so both variants can be A/B tested on
 * the device without rebuilding/re-transferring the module:
 *
 *   modprobe panel_xiaomi_olive_nt36525b non_cont_clk=0   -> continuous clock
 *   modprobe panel_xiaomi_olive_nt36525b non_cont_clk=1   -> non-continuous
 *
 * The factory dtbo timings program the 12nm PHY's own CLKLANE_* state machine
 * for a continuously running clock lane.  With MIPI_DSI_CLOCK_NON_CONTINUOUS
 * the DSI controller also arbitrates the clock lane (HS_REQ_SEL_PHY stays
 * set), so two owners fight over the same lane and every data lane's HS FIFO
 * ends up latched in overflow+underflow (FIFO_STATUS 0xcccc1000), which shows
 * up as rainbow stripes.
 */
static bool non_cont_clk;
module_param(non_cont_clk, bool, 0644);
MODULE_PARM_DESC(non_cont_clk, "Use non-continuous DSI clock lane (default 0)");

static uint video_mode;
module_param(video_mode, uint, 0644);
MODULE_PARM_DESC(video_mode, "DSI video mode: 0=burst+nohbp 1=burst 2=sync-pulse 3=event");

static inline struct nt36525b *to_nt36525b(struct drm_panel *panel)
{
	return container_of_const(panel, struct nt36525b, panel);
}

static void nt36525b_reset(struct nt36525b *ctx)
{
	gpiod_set_value_cansleep(ctx->reset_gpio, 1);
	msleep(20);
	gpiod_set_value_cansleep(ctx->reset_gpio, 0);
	msleep(10);
	gpiod_set_value_cansleep(ctx->reset_gpio, 1);
	msleep(20);
}

static int nt36525b_on(struct nt36525b *ctx)
{
	struct mipi_dsi_multi_context dsi_ctx = { .dsi = ctx->dsi };

	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0xff, 0x20);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0xfb, 0x01);
	mipi_dsi_dcs_write_seq_multi(&dsi_ctx, 0xc0, 0x02, 0x03, 0x05, 0x06, 0x08, 0x0d, 0x0d, 0x0e, 0x0f, 0x10, 0x12, 0x40, 0x38, 0x24, 0x24, 0x2c);
	mipi_dsi_dcs_write_seq_multi(&dsi_ctx, 0xc2, 0x02, 0x03, 0x05, 0x06, 0x08, 0x0d, 0x0d, 0x0e, 0x0f, 0x10, 0x12, 0x12, 0x38, 0x24, 0x24, 0x2c);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0xff, 0x23);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0xfb, 0x01);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x00, 0x68);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x05, 0x12);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x06, 0x00);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x07, 0x20);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x08, 0x01);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x09, 0x00);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x12, 0xab);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x15, 0x7b);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x16, 0x0a);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x30, 0xff);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x31, 0xfe);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x32, 0xfc);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x33, 0xfa);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x34, 0xf8);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x35, 0xf6);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x36, 0xf4);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x37, 0xf2);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x38, 0xf1);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x39, 0xf0);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x3a, 0xef);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x3b, 0xed);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x3d, 0xeb);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x3f, 0xe9);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x40, 0xe7);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x41, 0xe5);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x45, 0xff);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x46, 0xfc);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x47, 0xf6);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x48, 0xec);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x49, 0xdf);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x4a, 0xcd);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x4b, 0xc0);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x4c, 0xb3);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x4d, 0xa6);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x4e, 0x98);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x4f, 0x8f);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x50, 0x86);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x51, 0x7d);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x52, 0x74);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x53, 0x6d);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x54, 0x66);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x58, 0xff);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x59, 0xfd);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x5a, 0xf9);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x5b, 0xf2);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x5c, 0xec);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x5d, 0xe6);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x5e, 0xde);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x5f, 0xd9);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x60, 0xd2);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x61, 0xcc);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x62, 0xc7);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x63, 0xc3);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x64, 0xbe);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x65, 0xb9);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x66, 0xb5);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x67, 0xb3);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0xff, 0x22);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0xfb, 0x01);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x01, 0x04);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x02, 0x08);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x03, 0x0c);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x04, 0x10);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x05, 0x14);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x06, 0x18);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x07, 0x20);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x08, 0x24);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x09, 0x28);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x0a, 0x30);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x0b, 0x38);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x0c, 0x38);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x0d, 0x30);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x0e, 0x28);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x0f, 0x20);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x10, 0x10);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x11, 0x00);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x12, 0x00);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x13, 0x00);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x1a, 0x00);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x1b, 0x00);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x1c, 0x04);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x1d, 0x08);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x1e, 0x0c);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x1f, 0x10);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x20, 0x14);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x21, 0x18);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x22, 0x20);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x23, 0x18);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x24, 0x10);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x25, 0x08);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x26, 0x00);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x27, 0x00);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x28, 0x00);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x29, 0x00);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x2a, 0x00);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x2b, 0x00);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x2f, 0x00);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x30, 0x00);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x31, 0x10);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x32, 0x9c);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x33, 0x94);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x34, 0x94);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x35, 0x1e);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x36, 0x14);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x37, 0x1e);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x38, 0x1e);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x39, 0x14);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x3a, 0x0a);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x3b, 0x0c);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x3f, 0x0e);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x40, 0x15);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x41, 0x1b);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x42, 0x20);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x43, 0x26);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x44, 0x1e);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x45, 0x17);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x46, 0x0f);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x47, 0x08);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x48, 0x0a);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x49, 0x12);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x4a, 0x23);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x4b, 0x28);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x4c, 0x9c);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x4d, 0x00);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x53, 0x00);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x54, 0x00);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x55, 0x00);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x56, 0x76);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x68, 0x76);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0xa2, 0x20);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0xff, 0x26);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0xfb, 0x01);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x45, 0x0e);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0xff, 0x10);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0xfb, 0x01);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x55, 0x80);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0xba, 0x03);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x51, 0x0f, 0xff);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x53, 0x2c);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x29, 0x00);
	mipi_dsi_msleep(&dsi_ctx, 20);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x11, 0x00);
	mipi_dsi_msleep(&dsi_ctx, 100);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0xff, 0x25);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0xfb, 0x01);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x24, 0xa7);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x46, 0x13);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x47, 0x94);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0xff, 0x26);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0xfb, 0x01);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x31, 0x11);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x32, 0x18);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x36, 0x67);
	mipi_dsi_dcs_exit_sleep_mode_multi(&dsi_ctx);
	mipi_dsi_msleep(&dsi_ctx, 120);
	mipi_dsi_dcs_set_display_on_multi(&dsi_ctx);
	mipi_dsi_msleep(&dsi_ctx, 32);
	return dsi_ctx.accum_err;
}

static int nt36525b_off(struct nt36525b *ctx)
{
	struct mipi_dsi_multi_context dsi_ctx = { .dsi = ctx->dsi };

	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0xff, 0x10);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0xfb, 0x01);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x28, 0x00);
	mipi_dsi_msleep(&dsi_ctx, 20);
	mipi_dsi_generic_write_seq_multi(&dsi_ctx, 0x10, 0x00);
	mipi_dsi_msleep(&dsi_ctx, 120);
	return dsi_ctx.accum_err;
}

static int nt36525b_prepare(struct drm_panel *panel)
{
	struct nt36525b *ctx = to_nt36525b(panel);
	struct device *dev = &ctx->dsi->dev;
	int ret;

	dev_info(dev, "olive: prepare begin (lanes=%u fmt=%u)\n",
		 ctx->dsi->lanes, ctx->dsi->format);

	nt36525b_reset(ctx);

	ret = nt36525b_on(ctx);
	dev_info(dev, "olive: init sequence done, ret=%d\n", ret);
	if (ret < 0) {
		dev_err(dev, "Failed to initialize panel: %d\n", ret);
		gpiod_set_value_cansleep(ctx->reset_gpio, 1);
		return ret;
	}

	return 0;
}

static int nt36525b_unprepare(struct drm_panel *panel)
{
	struct nt36525b *ctx = to_nt36525b(panel);
	struct device *dev = &ctx->dsi->dev;
	int ret;

	dev_info(dev, "olive: unprepare begin\n");

	ret = nt36525b_off(ctx);
	if (ret < 0)
		dev_err(dev, "Failed to un-initialize panel: %d\n", ret);

	gpiod_set_value_cansleep(ctx->reset_gpio, 1);

	return 0;
}

static const struct drm_display_mode nt36525b_mode = {
	.clock = (720 + 101 + 8 + 100) * (1520 + 10 + 2 + 8) * 60 / 1000,
	.hdisplay = 720,
	.hsync_start = 720 + 101,
	.hsync_end = 720 + 101 + 8,
	.htotal = 720 + 101 + 8 + 100,
	.vdisplay = 1520,
	.vsync_start = 1520 + 10,
	.vsync_end = 1520 + 10 + 2,
	.vtotal = 1520 + 10 + 2 + 8,
	.width_mm = 68,
	.height_mm = 143,
	.type = DRM_MODE_TYPE_DRIVER,
};

static int nt36525b_get_modes(struct drm_panel *panel,
			      struct drm_connector *connector)
{
	return drm_connector_helper_get_modes_fixed(connector, &nt36525b_mode);
}

static const struct drm_panel_funcs nt36525b_panel_funcs = {
	.prepare = nt36525b_prepare,
	.unprepare = nt36525b_unprepare,
	.get_modes = nt36525b_get_modes,
};

static int nt36525b_probe(struct mipi_dsi_device *dsi)
{
	struct device *dev = &dsi->dev;
	struct nt36525b *ctx;
	int ret;

	ctx = devm_drm_panel_alloc(dev, struct nt36525b, panel,
				   &nt36525b_panel_funcs,
				   DRM_MODE_CONNECTOR_DSI);
	if (IS_ERR(ctx))
		return PTR_ERR(ctx);

	ctx->reset_gpio = devm_gpiod_get(dev, "reset", GPIOD_OUT_HIGH);
	if (IS_ERR(ctx->reset_gpio))
		return dev_err_probe(dev, PTR_ERR(ctx->reset_gpio),
				     "Failed to get reset-gpios\n");

	ctx->dsi = dsi;
	mipi_dsi_set_drvdata(dsi, ctx);

	dsi->lanes = 4;
	dsi->format = MIPI_DSI_FMT_RGB888;

	/*
	 * Video-mode variants, switchable at load time:
	 *   0 = burst + no HBP   (factory configuration, default)
	 *   1 = burst + HBP
	 *   2 = non-burst, sync pulse
	 *   3 = non-burst, sync event
	 * The 4-lane RGB888 link has zero bandwidth margin at this pixel clock
	 * (4 x 515 Mbps == 720x1520@60 x 24bpp exactly), so the burst geometry
	 * has to be right or every line gets truncated.
	 */
	switch (video_mode) {
	case 1:
		dsi->mode_flags = MIPI_DSI_MODE_VIDEO | MIPI_DSI_MODE_VIDEO_BURST |
				  MIPI_DSI_MODE_VIDEO_HSE | MIPI_DSI_MODE_NO_EOT_PACKET |
				  MIPI_DSI_MODE_LPM;
		break;
	case 2:
		dsi->mode_flags = MIPI_DSI_MODE_VIDEO | MIPI_DSI_MODE_VIDEO_SYNC_PULSE |
				  MIPI_DSI_MODE_VIDEO_HSE | MIPI_DSI_MODE_NO_EOT_PACKET |
				  MIPI_DSI_MODE_LPM;
		break;
	case 3:
		dsi->mode_flags = MIPI_DSI_MODE_VIDEO |
				  MIPI_DSI_MODE_VIDEO_HSE | MIPI_DSI_MODE_NO_EOT_PACKET |
				  MIPI_DSI_MODE_LPM;
		break;
	default:
		dsi->mode_flags = MIPI_DSI_MODE_VIDEO | MIPI_DSI_MODE_VIDEO_BURST |
				  MIPI_DSI_MODE_VIDEO_HSE | MIPI_DSI_MODE_NO_EOT_PACKET |
				  MIPI_DSI_MODE_VIDEO_NO_HBP | MIPI_DSI_MODE_LPM;
		break;
	}

	if (non_cont_clk)
		dsi->mode_flags |= MIPI_DSI_CLOCK_NON_CONTINUOUS;

	dev_err(dev, "olive: mode_flags=0x%lx (video_mode=%u non_cont_clk=%u)\n",
		(unsigned long)dsi->mode_flags, video_mode, non_cont_clk);

	ctx->panel.prepare_prev_first = true;

	ret = drm_panel_of_backlight(&ctx->panel);
	if (ret)
		return dev_err_probe(dev, ret, "Failed to get backlight\n");

	drm_panel_add(&ctx->panel);

	ret = mipi_dsi_attach(dsi);
	if (ret < 0) {
		drm_panel_remove(&ctx->panel);
		return dev_err_probe(dev, ret, "Failed to attach to DSI host\n");
	}

	return 0;
}

static void nt36525b_remove(struct mipi_dsi_device *dsi)
{
	struct nt36525b *ctx = mipi_dsi_get_drvdata(dsi);
	int ret;

	ret = mipi_dsi_detach(dsi);
	if (ret < 0)
		dev_err(&dsi->dev, "Failed to detach from DSI host: %d\n", ret);

	drm_panel_remove(&ctx->panel);
}

static const struct of_device_id nt36525b_of_match[] = {
	{ .compatible = "xiaomi,olive-panel" },
	{ /* sentinel */ }
};
MODULE_DEVICE_TABLE(of, nt36525b_of_match);

static struct mipi_dsi_driver nt36525b_driver = {
	.probe = nt36525b_probe,
	.remove = nt36525b_remove,
	.driver = {
		.name = "panel-xiaomi-olive-nt36525b",
		.of_match_table = nt36525b_of_match,
	},
};
module_mipi_dsi_driver(nt36525b_driver);

MODULE_AUTHOR("WorkBuddy");
MODULE_DESCRIPTION("DRM driver for Xiaomi Redmi 8A (NT36525B 720x1520)");
MODULE_LICENSE("GPL");

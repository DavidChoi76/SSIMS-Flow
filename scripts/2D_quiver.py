"""
This is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This package is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this package. If not, you can get eh GNU GPL from
https://www.gnu.org/licenses/gpl-3.0.en.html.

Created by Robert Ljubicic.
"""

try:
	from __init__ import *
	from matplotlib.widgets import Slider
	from sys import exit
	from glob import glob
	from class_console_printer import tag_print, unix_path
	from utilities import cfg_get, exit_message, present_exception_and_exit

	import matplotlib.pyplot as plt

except Exception as ex:
	present_exception_and_exit('Import failed! For more information see traceback below. Please report this issue to the author:')


def update_vmax(val):
	quiver.set_clim(vmax=sl_ax_vmax.val)
	plt.draw()


def update_quiver_scale(val):
	quiver_scale_factor = sl_ax_scale.val
	quiver_scale = np.max(mags) / quiver_scale_factor
	quiver.scale = quiver_scale
	plt.draw()


def update_slider(val):
	mags = try_load_file(mag_list[val]) * v_ratio
	dirs = try_load_file(dir_list[val])
	us, vs = cv2.polarToCart(mags, dirs, angleInDegrees=True)

	if frames_available:
		back_new = cv2.imread(frames_list[val], cv2.COLOR_BGR2RGB)[::-1]
		back_shown.set_data(back_new)

	quiver.set_data(xs, ys, us, -vs, mags)
	quiver.set_clim(vmin=np.nanmin(mags[cbar_cutoff_h: -cbar_cutoff_h, cbar_cutoff_w: -cbar_cutoff_w]),
					vmax=np.nanmax(mags[cbar_cutoff_h: -cbar_cutoff_h, cbar_cutoff_w: -cbar_cutoff_w]))
	
	ax.set_title(f'{data_type}, frame #{sl_ax_vmax.val}/{num_frames - 1}')
	plt.draw()

	return


def keypress(event):
	if event.key == 'escape':
		exit()

	elif event.key == 'down':
		if sl_ax_vmax.val == 0:
			sl_ax_vmax.set_val(num_frames - 1)
		else:
			sl_ax_vmax.set_val(sl_ax_vmax.val - 1)

	elif event.key == 'up':
		if sl_ax_vmax.val == num_frames - 1:
			sl_ax_vmax.set_val(0)
		else:
			sl_ax_vmax.set_val(sl_ax_vmax.val + 1)

	elif event.key == 'pageup':
		if sl_ax_vmax.val >= num_frames - 10:
			sl_ax_vmax.set_val(0)
		else:
			sl_ax_vmax.set_val(sl_ax_vmax.val + 10)

	elif event.key == 'pagedown':
		if sl_ax_vmax.val <= 9:
			sl_ax_vmax.set_val(num_frames - 1)
		else:
			sl_ax_vmax.set_val(sl_ax_vmax.val - 10)

	update_slider(sl_ax_vmax.val)


def try_load_file(fname):
	try:
		return np.loadtxt(fname)
	except Exception:
		return None
	

def vector_coords(size, step):
	num_vectors = int(size // step)
	coords = np.ndarray([num_vectors], dtype=float)
	res = (size % step) // 2

	start = res + step // 2

	for i in range(num_vectors):
		coords[i] = (start + i * step)

	return coords


if __name__ == '__main__':
	try:
		parser = ArgumentParser()
		parser.add_argument('--cfg', type=str, help='Path to project configuration file')
		parser.add_argument('--mode', type=int, help='0 = time averaged, 1 = maximal, 2 = instantaneous', default=0)
		args = parser.parse_args()

		cfg = configparser.ConfigParser()
		cfg.optionxform = str

		try:
			cfg.read(args.cfg, encoding='utf-8-sig')
		except Exception:
			tag_print('error', 'There was a problem reading the configuration file!')
			tag_print('error', 'Check if project has valid configuration.')
			exit_message()

		plot_mode = args.mode
		data_type = 'Flow vectors'
		units = 'm/s'
		project_folder = unix_path(cfg_get(cfg, 'Project settings', 'Folder', str))

		section = 'Optical flow'

		frames_step = cfg_get(cfg, 'Frames', 'Step', float)
		optical_flow_step = cfg_get(cfg, section, 'Step', float)
		scale = cfg_get(cfg, section, 'Scale', float)
		fps = cfg_get(cfg, section, 'Framerate', float)		# frames/sec

		try:
			gsd = cfg_get(cfg, section, 'GSD', float)       # px/m
		except Exception as ex:
			gsd = cfg_get(cfg, 'Transformation', 'GSD', float)        # px/m

		gsd_units = cfg_get(cfg, section, 'GSDUnits', str, 'px/m')           # px/m
		
		if gsd_units != 'px/m':
			gsd = 1/gsd
			
		pooling = cfg_get(cfg, section, 'Pooling', float)   	# px
		gsd_pooled = gsd / pooling  				# blocks/m, 1/m

		v_ratio = fps / gsd / (frames_step * optical_flow_step) / scale         	# (frame*m) / (s*px)

		average_only = cfg_get(cfg, section, 'AverageOnly', int)    # px
		frames_folder = cfg_get(cfg, section, 'Folder', str)
		frames_ext = cfg_get(cfg, 'section', 'Extension', str, 'jpg')
		frames_list = glob(f'{frames_folder}/*.{frames_ext}')
		frames_available = len(frames_list) > 0

		if average_only == 0:
			mag_list = glob(f'{project_folder}/optical_flow/magnitudes/*.txt')
			dir_list = glob(f'{project_folder}/optical_flow/directions/*.txt')
			num_frames = len(mag_list)

			if num_frames == 0:
				print()
				tag_print('error', f'No optical flow data found in [{project_folder}/optical_flow/]')
				exit_message()

		fig, ax = plt.subplots()
		plt.subplots_adjust(bottom=0.15)
		plt.axis('off')

		legend = 'Use slider to select frame,\n' \
				 'use UP and DOWN keys to move by +/- 1 frame\n' \
				 'or PageUP and PageDOWN keys to move by +/- 10 frames\n' \
				 'Press ESC or Q to exit'

		legend_toggle = plt.text(0.02, 0.97, legend,
								 horizontalalignment='left',
								 verticalalignment='top',
								 transform=ax.transAxes,
								 bbox=dict(facecolor='white', alpha=0.5),
								 fontsize=9,
								 )
		
		if plot_mode == 0:       # Time averaged
			legend_toggle.set_visible(False)

			mags = try_load_file(f'{project_folder}/optical_flow/mag_mean.txt') * v_ratio	# px/frame
			dirs = try_load_file(f'{project_folder}/optical_flow/angle_mean.txt')
			h, w = mags.shape

			us, vs = cv2.polarToCart(mags, dirs, angleInDegrees=True)

		elif plot_mode == 1:     # Maximal
			legend_toggle.set_visible(False)

			mags = try_load_file(f'{project_folder}/optical_flow/mag_max.txt') * v_ratio	# px/frame
			dirs = try_load_file(f'{project_folder}/optical_flow/angle_mean.txt')
			h, w = mags.shape

			us, vs = cv2.polarToCart(mags, dirs, angleInDegrees=True)

		# elif plot_mode == 2:     # Instantaneous  
		#     mags = try_load_file(mag_list[0]) * v_ratio
		#     dirs = try_load_file(dir_list[0])
		#     h, w = mags.shape

		#     us, vs = cv2.polarToCart(mags, dirs, angleInDegrees=True)

		#     axcolor = 'lightgoldenrodyellow'
		#     valfmt = "%d"

		#     fig.canvas.mpl_connect('key_press_event', keypress)
		#     ax_vmax = plt.axes([0.2, 0.05, 0.63, 0.03], facecolor=axcolor)
		#     sl_ax_vmax = Slider(ax_vmax, 'Frame #', 0, num_frames-1, valinit=0, valstep=1, valfmt=valfmt)
		#     sl_ax_vmax.on_changed(update_slider)

		cbar_cutoff_h = h//5
		cbar_cutoff_w = w//5

		xs, ys = np.meshgrid([x+0.5 for x in range(w)], [y+0.5 for y in range(h)])

		if plot_mode in [0, 1]:
			axcolor = 'lightgoldenrodyellow'
			valfmt = "%.3f"

			ax_vmax = plt.axes([0.2, 0.10, 0.63, 0.03], facecolor=axcolor)

			real_max = np.nanmax(mags)
			cut_max = np.nanmax(mags[cbar_cutoff_h: -cbar_cutoff_h, cbar_cutoff_w: -cbar_cutoff_w])

			sl_ax_vmax = Slider(ax_vmax, 'Max. value [m/s]', np.nanmin(mags), np.nanmax(mags), valinit=cut_max, valstep=real_max/100, valfmt=valfmt)
			sl_ax_vmax.on_changed(update_vmax)

		axcolor = 'lightgoldenrodyellow'
		valfmt = "%.1f"

		ax_scale = plt.axes([0.2, 0.05, 0.63, 0.03], facecolor=axcolor)

		sl_ax_scale = Slider(ax_scale, 'Vector scale [-]', 0.1, 10, valinit=1, valstep=0.1, valfmt=valfmt)
		sl_ax_scale.on_changed(update_quiver_scale)

		if frames_available:
			back = cv2.imread(frames_list[0], cv2.COLOR_BGR2RGB)[::-1]
			padd_x = (back.shape[1] % pooling) / 2 / pooling / scale
			padd_y = (back.shape[0] % pooling) / 2 / pooling / scale

			extent = (-padd_x, w + padd_x, -padd_y, h + padd_y)
			back_shown = ax.imshow(back, extent=extent, zorder=-2)

		ghost_plot = ax.imshow(mags, zorder=-1, alpha=0)

		quiver_scale_factor = 1.0
		quiver_scale = np.max(mags) / quiver_scale_factor
		quiver = ax.quiver(xs, ys, us, vs, mags, cmap='jet', scale=quiver_scale, scale_units='xy', angles='xy', zorder = 0)
		quiver.set_clim(vmin=np.nanmin(mags[cbar_cutoff_h: -cbar_cutoff_h, cbar_cutoff_w: -cbar_cutoff_w]),
						vmax=np.nanmax(mags[cbar_cutoff_h: -cbar_cutoff_h, cbar_cutoff_w: -cbar_cutoff_w]))

		cbar = plt.colorbar(quiver, ax=ax)
		cbar.ax.set_ylabel('Velocity magnitude [m/s]', rotation=90)

		try:
			mng = plt.get_current_fig_manager()
			mng.window.state('zoomed')
			mng.set_window_title('Inspect frames')
		except Exception:
			pass

		ax.set_title(f'{data_type}, frame #0/{num_frames - 1}'
					 if plot_mode == 2
					 else f'Time averaged values: {data_type}')
		# ax.invert_yaxis()
		plt.show()

	except Exception as ex:
		present_exception_and_exit()

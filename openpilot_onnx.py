import cv2
import json
import numpy as np
import onnxruntime
import pandas as pd
import os

from matplotlib import pyplot as plt

X_IDXS = np.array([ 0. ,   0.1875,   0.75  ,   1.6875,   3.    ,   4.6875,
         6.75  ,   9.1875,  12.    ,  15.1875,  18.75  ,  22.6875,
        27.    ,  31.6875,  36.75  ,  42.1875,  48.    ,  54.1875,
        60.75  ,  67.6875,  75.    ,  82.6875,  90.75  ,  99.1875,
       108.    , 117.1875, 126.75  , 136.6875, 147.    , 157.6875,
       168.75  , 180.1875, 192.])

def parse_image(frame):
	H = (frame.shape[0]*2)//3
	W = frame.shape[1]
	parsed = np.zeros((6, H//2, W//2), dtype=np.uint8)

	parsed[0] = frame[0:H:2, 0::2]
	parsed[1] = frame[1:H:2, 0::2]
	parsed[2] = frame[0:H:2, 1::2]
	parsed[3] = frame[1:H:2, 1::2]
	parsed[4] = frame[H:H+H//4].reshape((-1, H//2,W//2))
	parsed[5] = frame[H+H//4:H+H//2].reshape((-1, H//2,W//2))

	return parsed

def get_probabilities(probabilities):
	x = np.exp(probabilities) / np.sum(np.exp(probabilities))
	return x

def get_mean_velocity(plan, probabiltiies):
	x_vels = []
	y_vels = []
	z_vels = []

	for i in range(3, 495, 15):
		total = 0
		for j in range(5):
			total += plan[:,:,3 + 991*j + i].item() * probabiltiies[j]
		x_vels.append(total)
	for i in range(4, 495, 15):
		total = 0
		for j in range(5):
			total += plan[:,:,4 + 991*j + i].item() * probabiltiies[j]
		y_vels.append(total)
	for i in range(5, 495, 15):
		total = 0
		for j in range(5):
			total += plan[:, :, 5 + 991*j + i].item() * probabiltiies[j]
		z_vels.append(total)
	
	return x_vels, y_vels, z_vels

def get_mean_position(plan, probabiltiies):
	x_pos = []
	y_pos = []
	z_pos = []

	for i in range(0, 495, 15):
		total = 0
		for j in range(5):
			total += plan[:,:,991*j + i].item() * probabiltiies[j]
		x_pos.append(total)
	for i in range(1, 495, 15):
		total = 0
		for j in range(5):
			total += plan[:,:,1 + 991*j + i].item() * probabiltiies[j]
		y_pos.append(total)
	for i in range(2, 495, 15):
		total = 0
		for j in range(5):
			total += plan[:,:,2 + 991*j + i].item() * probabiltiies[j]
		z_pos.append(total)
	
	return x_pos, y_pos, z_pos

def seperate_points_and_std_values(df):
	points = df.iloc[lambda x: x.index % 2 == 0]
	std = df.iloc[lambda x: x.index % 2 != 0]
	points = pd.concat([points], ignore_index = True)
	std = pd.concat([std], ignore_index = True)

	return points, std

def main(traffic_value, desire_value, flipped):
	model = "supercombo.onnx"
	image_folder = 'data/images/'
	velocity_folder = 'data/velocity/'
	position_folder = 'data/position'
	if flipped:
		output_folder = f'data_flipped/plot_images_{traffic_value}_{desire_value}/'
	else:
		output_folder = f'data/plot_images_{traffic_value}_{desire_value}/'
		
	## velocity_folder = f'data_flipped/velocity_plots_{traffic_value}_{desire_value}/'
	os.makedirs(output_folder, exist_ok=True)
	images = sorted([img for img in os.listdir(image_folder)])
	## cap = cv2.VideoCapture('data/cropped_plats.mp4')
	parsed_images = []

	width = 512
	height = 256
	dim = (width, height)
	
	plan_start_idx = 0
	plan_end_idx = 4955
	
	lanes_start_idx = plan_end_idx
	lanes_end_idx = lanes_start_idx + 528
	
	lane_lines_prob_start_idx = lanes_end_idx
	lane_lines_prob_end_idx = lane_lines_prob_start_idx + 8
	
	road_start_idx = lane_lines_prob_end_idx
	road_end_idx = road_start_idx + 264

# 	lead_start_idx = road_end_idx
# 	lead_end_idx = lead_start_idx + 55
# 	
# 	lead_prob_start_idx = lead_end_idx
# 	lead_prob_end_idx = lead_prob_start_idx + 3
# 	
# 	desire_start_idx = lead_prob_end_idx
# 	desire_end_idx = desire_start_idx + 72
# 	
# 	meta_start_idx = desire_end_idx
# 	meta_end_idx = meta_start_idx + 32
# 	
# 	desire_pred_start_idx = meta_end_idx
# 	desire_pred_end_idx = desire_pred_start_idx + 32
# 	
# 	pose_start_idx = desire_pred_end_idx
# 	pose_end_idx = pose_start_idx + 12
# 	
# 	rnn_start_idx = pose_end_idx
# 	rnn_end_idx = rnn_start_idx + 908
	
	session = onnxruntime.InferenceSession(model, None)
	for image in images:
		img_path = os.path.join(image_folder, image)
		frame = cv2.imread(img_path)

		if frame is None:
			print(F"Unable to read {img_path}")
			continue

		if frame is not None:
			if flipped:
				frame = cv2.flip(frame, 1)
			img = cv2.resize(frame, dim)
			img_yuv = cv2.cvtColor(img, cv2.COLOR_BGR2YUV_I420)
			parsed = parse_image(img_yuv)
	
		if (len(parsed_images) >= 2):
			del parsed_images[0]
	
		parsed_images.append(parsed)

		if (len(parsed_images) >= 2):
		
			parsed_arr = np.array(parsed_images)
			parsed_arr.resize((1,12,128,256))

			data = json.dumps({'data': parsed_arr.tolist()})
			data = np.array(json.loads(data)['data']).astype('float32')
			
			input_imgs = session.get_inputs()[0].name
			desire = session.get_inputs()[1].name
			initial_state = session.get_inputs()[2].name
			traffic_convention = session.get_inputs()[3].name
			output_name = session.get_outputs()[0].name
			
			##desire_data = np.array([0]).astype('float32')
			##desire_data.resize((1,8))
			desire_data = np.zeros((1, 8), dtype = np.float32)
			desire_data[0, desire_value] = 1
			
			##traffic_convention_data = np.array([0]).astype('float32')
			##traffic_convention_data.resize((1,512))
			initial_state_data = np.zeros((1, 2), dtype = np.float32)
			initial_state_data[0, traffic_value] = 1
			##traffic_convention_data = np.full((1, 512), traffic_value, dtype = np.float32)
			
			##initial_state_data = np.array([0, 0]).astype('float32').reshape((1, 2))
			##initial_state_data.resize((1,2))
			traffic_convention_data = np.zeros((1, 512), dtype = np.float32)

			result = session.run([output_name], {input_imgs: data,
												desire: desire_data,
												traffic_convention: traffic_convention_data,
												initial_state: initial_state_data
												})

			res = np.array(result)

			plan = res[:,:,plan_start_idx:plan_end_idx]
			probabilities = get_probabilities(np.array([plan[:,:,990].item(), plan[:,:,1981].item(), plan[:,:,2972].item(), plan[:,:,3963].item(), plan[:,:,4954].item()]))
			lanes = res[:,:,lanes_start_idx:lanes_end_idx]
			# lane_lines_prob = res[:,:,lane_lines_prob_start_idx:lane_lines_prob_end_idx]
			lane_road = res[:,:,road_start_idx:road_end_idx]
			# lead = res[:,:,lead_start_idx:lead_end_idx]
			# lead_prob = res[:,:,lead_prob_start_idx:lead_prob_end_idx]
			# desire_state = res[:,:,desire_start_idx:desire_end_idx]
			# meta = res[:,:,meta_start_idx:meta_end_idx]
			# desire_pred = res[:,:,desire_pred_start_idx:desire_pred_end_idx]
			# pose = res[:,:,pose_start_idx:pose_end_idx]
			# recurrent_layer = res[:,:,rnn_start_idx:rnn_end_idx]

			lanes_flat = lanes.flatten()
			df_lanes = pd.DataFrame(lanes_flat)

			ll_t = df_lanes[0:66]
			ll_t2 = df_lanes[66:132]
			points_ll_t, std_ll_t = seperate_points_and_std_values(ll_t)
			points_ll_t2, std_ll_t2 = seperate_points_and_std_values(ll_t2)

			l_t = df_lanes[132:198]
			l_t2 = df_lanes[198:264]
			points_l_t, std_l_t = seperate_points_and_std_values(l_t)
			points_l_t2, std_l_t2 = seperate_points_and_std_values(l_t2)

			r_t = df_lanes[264:330]
			r_t2 = df_lanes[330:396]
			points_r_t, std_r_t = seperate_points_and_std_values(r_t)
			points_r_t2, std_r_t2 = seperate_points_and_std_values(r_t2)

			rr_t = df_lanes[396:462]
			rr_t2 = df_lanes[462:528]
			points_rr_t, std_rr_t = seperate_points_and_std_values(rr_t)
			points_rr_t2, std_rr_t2 = seperate_points_and_std_values(rr_t2)

			road_flat = lane_road.flatten()
			df_road = pd.DataFrame(road_flat)

			roadr_t = df_road[0:66]
			roadr_t2 = df_road[66:132]
			points_road_t, std_ll_t = seperate_points_and_std_values(roadr_t)
			points_road_t2, std_ll_t2 = seperate_points_and_std_values(roadr_t2)

			roadl_t = df_road[132:198]
			roadl_t2 = df_road[198:264]
			points_roadl_t, std_rl_t = seperate_points_and_std_values(roadl_t)
			points_roadl_t2, std_rl_t2 = seperate_points_and_std_values(roadl_t2)

			middle = points_ll_t2.add(points_l_t, fill_value=0) / 2

			# plt.scatter(middle, X_IDXS, color = "g", s = 1)
			# plt.ylim(0, 100)
			# plt.scatter(points_ll_t, X_IDXS, color = "b", marker = "*")
			# plt.scatter(points_ll_t2, X_IDXS, color = "y", s = 1)

			# plt.scatter(points_l_t, X_IDXS, color = "y", s = 1)
			# ##plt.scatter(points_l_t2, X_IDXS, color = "y", marker = "*")

			# plt.scatter(points_road_t, X_IDXS, color = "r", s = 1)
			# plt.scatter(points_road_t2, X_IDXS, color = "r", s = 1)

			# plt.title("Raod lines")
			# plt.xlabel("red - road lines | green - predicted path | yellow - lane lines")
			# plt.ylabel("Range")
			# plot_filename = os.path.join(output_folder, f"plot_{os.path.splitext(image)[0]}.png")
			# plt.savefig(plot_filename)
			# plt.clf()

			x_vel, y_vel, z_vel = get_mean_velocity(plan, probabilities)
			x_pos, y_pos, z_pos = get_mean_position(plan, probabilities)
			y_pos = [y * -1 for y in y_pos]
			y_vel = [y * -1 for y in y_vel]
			plt.quiver(y_pos, X_IDXS, y_vel, x_vel, scale=5)
			plt.ylim(0, 10)
			plt.xlim(-5, 5)
			plt.xlabel("Y Position")
			plt.ylabel("X Position")
			plot_filename = os.path.join(velocity_folder, f"plot_{os.path.splitext(image)[0]}.png")
			plt.savefig(plot_filename)
			plt.clf()

			plt.scatter(y_pos, X_IDXS)
			plt.ylim(0, 10)
			plt.xlim(-5, 5)
			plt.xlabel("Y Position")
			plt.ylabel("X Position")
			plot_filename = os.path.join(position_folder, f"plot_{os.path.splitext(image)[0]}.png")
			plt.savefig(plot_filename)
			plt.clf()

		frame = cv2.resize(frame, (900, 500))
		##cv2.imshow('frame', frame)

		if cv2.waitKey(1) & 0xFF == ord('q'):
			break

	cv2.destroyAllWindows()
	print(f"Done")

if __name__ == "__main__":
	for x in range(1):
		for y in range(1):
			main(x, y, False)
			print("done")